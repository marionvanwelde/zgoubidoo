"""Provides an interface to run Zgoubi from Python; supports multiprocessing and concurrent programming.

.. seealso::

    The full `Zgoubi User Guide`_ can also be consulted for reference.

    .. _Zgoubi User Guide: https://sourceforge.net/projects/zgoubi/

"""
from __future__ import annotations
from typing import TYPE_CHECKING, List, Mapping, Iterable, Optional, Tuple, Union
import logging
import tempfile
import os
import numpy as _np
import pandas as _pd
from .executable import Executable
from .output.zgoubi import read_plt_file, read_matrix_file, read_srloss_file, read_srloss_steps_file, read_optics_file
from . import ureg as _ureg
import zgoubidoo
from .constants import ZGOUBI_INPUT_FILENAME as _ZGOUBI_INPUT_FILENAME
if TYPE_CHECKING:
    from .input import Input as _Input
    from .input import MappedParametersType as _MappedParametersType
    from .input import MappedParametersListType as _MappedParametersListType

__all__ = ['ZgoubiException', 'ZgoubiResults', 'Zgoubi']
_logger = logging.getLogger(__name__)


class ZgoubiException(Exception):
    """Exception raised for errors when running Zgoubi."""

    def __init__(self, m):
        self.message = m


class ZgoubiResults:
    """Results from a Zgoubi executable run."""
    def __init__(self, results: List[Mapping], options: Optional[Mapping] = None):
        """
        `ZgoubiResults` is used to store results and outputs from a single or multiple Zgoubi runs. It is instanciated
        from a list of dictionnaries containing the results (each one being a mapping between `MappedParameters`
        (to identify from which run the results are from) and the results themselves (also a dictionnary)).

        Methods and properties of `ZgoubiResults` are used to access and process individual or multiple results. In
        particular it is possible to extract a set of tracks from the results.

        Examples:
            >>> 1 + 1 # TODO

        Args:
            results: a list of dictionnaries structure with the Zgoubi run information and errors.
            options:
        """
        self._options: Mapping = options or {}
        self._results: List[Mapping] = results
        self._tracks: Optional[_pd.DataFrame] = None
        self._matrix: Optional[_pd.DataFrame] = None
        self._optics: Optional[_pd.DataFrame] = None
        self._srloss: Optional[_pd.DataFrame] = None
        self._srloss_steps: Optional[_pd.DataFrame] = None

    @classmethod
    def merge(cls, *results: ZgoubiResults):
        """Merge multiple ZgoubiResults into one.

        Args:
            results: list of `ZgoubiResults` to copy

        Returns:
            a new `ZgoubiResults` instance containing the concatenated results.
        """
        return cls([rr for r in results for rr in r._results])

    def __len__(self) -> int:
        """Length of the results list."""
        return len(self._results)

    def __copy__(self) -> ZgoubiResults:
        """Shallow copy operation."""
        return ZgoubiResults(self._results)

    def __getitem__(self, item: int):
        """Retrieve results from the list using a numeric index."""
        return self._results[item]

    def get_tracks(self,
                   parameters: Optional[_MappedParametersListType] = None,
                   force_reload: bool = False,
                   with_rays: bool = True,
                   with_survey: bool = True,
                   ) -> _pd.DataFrame:
        """
        Collects all tracks from the different Zgoubi instances matching the given parameters list
        in the results and concatenate them.

        Args:
            parameters:
            force_reload:
            with_rays:
            with_survey:

        Returns:
            A concatenated DataFrame with all the tracks in the result matching the parameters list.
        """
        if self._tracks is not None and parameters is None and force_reload is False:
            return self._tracks
        tracks = list()
        particle_id = 0
        for k, r in self.results:
            if parameters is None or k in parameters:
                try:
                    try:
                        p = r['path'].name
                    except AttributeError:
                        p = r['path']
                    tracks.append(read_plt_file(path=p))
                    tracks[-1]['IT'] += particle_id
                    particle_id = _np.max(tracks[-1]['IT'])
                    for kk, vv in k.items():
                        try:
                            tracks[-1][f"{kk.replace('.', '__')}"] = _ureg.Quantity(vv).to_base_units().m
                        except _ureg.UndefinedUnitError:
                            tracks[-1][f"{kk}"] = vv
                except FileNotFoundError:
                    _logger.warning(
                        f"Unable to read and load the Zgoubi .plt files required to collect the tracks for path "
                        "{r['path']}."
                    )
                    continue
        if len(tracks) > 0:
            tracks = _pd.concat(tracks, sort=False)
        else:
            tracks = _pd.DataFrame()
        if parameters is None:
            self._tracks = tracks
        if with_rays:
            zgoubidoo.surveys.construct_rays(tracks=tracks)
        if with_survey:
            zgoubidoo.surveys.transform_tracks(beamline=self.results[0][1]['input'],
                                               tracks=tracks,
                                               )
        return tracks

    @property
    def tracks(self) -> _pd.DataFrame:
        """
        Collects all tracks from the different Zgoubi instances in the results and concatenate them.

        Returns:
            A concatenated DataFrame with all the tracks in the result.
        """
        return self.get_tracks()

    def get_srloss(self,
                   parameters: Optional[_MappedParametersListType] = None,
                   force_reload: bool = False) -> _pd.DataFrame:
        """

        Args:
            parameters:
            force_reload:

        Returns:

        """
        if self._srloss is not None and parameters is None and force_reload is False:
            return self._srloss
        srloss = list()
        for k, r in self.results:
            if parameters is None or k in parameters:
                try:
                    try:
                        p = r['path'].name
                    except AttributeError:
                        p = r['path']
                    srloss.append(read_srloss_file(path=p))
                    for kk, vv in k.items():
                        srloss[-1][f"{kk}"] = vv
                except FileNotFoundError:
                    _logger.warning(
                        "Unable to read and load the Zgoubi SRLOSS files required to collect the SRLOSS data."
                    )
                    continue
        if len(srloss) > 0:
            srloss = _pd.concat(srloss)
        else:
            srloss = _pd.DataFrame()
        if parameters is None:
            self._srloss = srloss
        return srloss

    @property
    def srloss(self) -> _pd.DataFrame:
        """

        Returns:

        """
        return self.get_srloss()

    def get_srloss_steps(self,
                         parameters: Optional[_MappedParametersListType] = None,
                         force_reload: bool = False,
                         with_survey: bool = True) -> _pd.DataFrame:
        """

        Args:
            parameters:
            force_reload: the data are cached in most cases to allow multiple calls, this flag will force the data to
            be reloaded.
            with_survey: performs the transformation of the coordinates using the survey information (this is
            basically a transformation from the local coordinates of the element to the global reference frame).

        Returns:

        """
        if self._srloss_steps is not None and parameters is None and force_reload is False:
            return self._srloss_steps
        srloss_steps = list()
        for k, r in self.results:
            if parameters is None or k in parameters:
                try:
                    try:
                        p = r['path'].name
                    except AttributeError:
                        p = r['path']
                    srloss_steps.append(read_srloss_steps_file(path=p))
                    for kk, vv in k.items():
                        srloss_steps[-1][f"{kk}"] = vv
                except FileNotFoundError:
                    _logger.warning(
                        "Unable to read and load the Zgoubi SRLOSS_STEPS files required to collect "
                        "the SRLOSS STEPS data."
                    )
                    continue
        if len(srloss_steps) > 0:
            srloss_steps = _pd.concat(srloss_steps)
        else:
            srloss_steps = _pd.DataFrame()
        if parameters is None:
            self._srloss_steps = srloss_steps
        if with_survey and not srloss_steps.empty:
            zgoubidoo.surveys.transform_tracks(beamline=self.results[0][1]['input'],
                                               tracks=srloss_steps,
                                               )
        return srloss_steps

    @property
    def srloss_steps(self) -> _pd.DataFrame:
        """

        Returns:

        """
        return self.get_srloss_steps()

    @property
    def matrix(self) -> Optional[_pd.DataFrame]:
        """
        Collects all matrix data from the different Zgoubi instances in the results and concatenate them.

        Returns:
            A concatenated DataFrame with all the matrix information from the previous run.
        """
        if self._matrix is None:
            try:
                m = list()
                for r in self._results:
                    try:
                        p = r['path'].name
                    except AttributeError:
                        p = r['path']
                    m.append(read_matrix_file(path=p))
                self._matrix = _pd.concat(m)
            except FileNotFoundError:
                _logger.warning(
                    "Unable to read and load the Zgoubi MATRIX files required to collect the matrix data."
                )
                return None
        return self._matrix

    def get_optics(self,
                   force_reload: bool = False,
                   ) -> Optional[_pd.DataFrame]:
        """
        Collects all optics data from the different Zgoubi instances in the results and concatenate them.

        Args:
            force_reload:
        Returns:
            A concatenated DataFrame with all the optics information from the previous run.
        """
        if self._optics is not None and force_reload is False:
            return self._optics
        try:
            m = list()
            for r in self._results:
                try:
                    p = r['path'].name
                except AttributeError:
                    p = r['path']
                m.append(read_optics_file(path=p))
            self._optics = _pd.concat(m)
        except FileNotFoundError:
            _logger.warning(
                    "Unable to read and load the Zgoubi OPTICS files required to collect the matrix data."
                )
            return None
        return self._optics

    @property
    def optics(self) -> _pd.DataFrame:
        """

        Returns:

        """
        return self.get_optics()

    @property
    def results(self) -> List[Tuple[_MappedParametersType, Mapping]]:
        """Raw information from the Zgoubi run.

        Provides the raw data structures from the Zgoubi runs.

        Returns:
            a list of mappings.
        """
        return [(r['mapping'], r) for r in self._results]

    @property
    def paths(self) -> List[Tuple[_MappedParametersType, Union[str, tempfile.TemporaryDirectory]]]:
        """Path of all the directories for the runs present in the results.

        Returns:
            a list of directories.
        """
        return [(m, r['path']) for m, r in self.results]

    @property
    def mappings(self) -> List[_MappedParametersType]:
        """Parametric mappings of all the runs present in the results.

        Returns:
            a list of parametric mappings.
        """
        return [m for m, r in self.results]

    def save(self, destination: str = '.', what: Optional[List[str]] = None):
        """Save files.

        Args:
            destination:
            what:
        """
        files = what or [
            _ZGOUBI_INPUT_FILENAME,
            Zgoubi.RESULT_FILE,
        ]
        self.results[0][1]['input'].save(destination=destination, what=files)

    def print(self, what: str = 'result'):
        """Helper function to print the raw results from a Zgoubi run."""
        for m, r in self.results:
            print(f"Results for mapping {m}\n")
            print('\n'.join(r[what]))
            print("================================================================================================")
            print("================================================================================================")
            print("================================================================================================")


class Zgoubi(Executable):
    """High level interface to run Zgoubi from Python."""

    EXECUTABLE_NAME: str = 'zgoubi'
    """Default name of the Zgoubi executable."""

    INPUT_FILENAME: str = _ZGOUBI_INPUT_FILENAME
    """Name of the input file (typically zgoubi.dat)."""

    RESULT_FILE: str = 'zgoubi.res'
    """Default name of the Zgoubi result '.res' file."""

    def __init__(self, executable: str = EXECUTABLE_NAME, path: str = None, n_procs: Optional[int] = None):
        """
        `Zgoubi` is responsible for running the Zgoubi executable within Zgoubidoo. It will run Zgoubi as a subprocess
        and offers a variety of concurency and parallelisation features.

        The `Zgoubi` object is an interface to the Zgoubi executable. The executable can be found automatically or its
        name and path can be specified.

        The Zgoubi executable is called on an instance of `Input` specifying a list of paths containing Zgoubi input
        files. Multiple instances can thus be run in parallel.

        TODO details on concurrency

        Args:
            - executable: name of the Zgoubi executable
            - path: path to the Zgoubi executable
            - n_procs: maximum number of Zgoubi simulations to be started in parallel

        """
        super().__init__(executable=executable, results_type=ZgoubiResults, path=path, n_procs=n_procs)

    def _extract_output(self, path, code_input: _Input, mapping) -> List[str]:
        """Extract element by element output"""
        try:
            result = open(os.path.join(path, self.RESULT_FILE)).read().split('\n')
        except FileNotFoundError:
            # TODO add debug mechanism in this case
            raise ZgoubiException(f"Zgoubi execution ended but result '{self.RESULT_FILE}' file not found.")

        for e in code_input.line:
            e.attach_output(outputs=Zgoubi.find_labeled_output(result, e.LABEL1, e.KEYWORD),
                            zgoubi_input=code_input,
                            parameters=mapping,
                            )
        return result

    @staticmethod
    def find_labeled_output(out: Iterable[str], label: str, keyword: str) -> List[str]:
        """
        Process the Zgoubi output and retrieves output data for a particular labeled element.

        Args:
            - out: the Zgoubi output
            - label: the label of the element to be retrieved
            - keyword:

        Returns:
            the output of the given label
        """
        data: List[str] = []
        for l in out:
            if ' ' + label + ' ' in l and 'Keyword' in l and keyword in l:  # This might be a bit fragile
                data.append(l)
                continue
            if len(data) > 0:
                if '****' in l:  # This might be a bit fragile
                    break
                data.append(l)
        return list(filter(lambda _: len(_), data))
