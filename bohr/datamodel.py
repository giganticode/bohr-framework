from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Type

from dask.dataframe import DataFrame
from snorkel.map import BaseMapper


class ArtifactMapper(BaseMapper, ABC):
    @abstractmethod
    def get_artifact(self) -> Type:
        pass


@dataclass
class DatasetLoader(ABC):
    test_set: bool
    mapper: ArtifactMapper

    def get_artifact(self) -> Type:
        return self.get_mapper().get_artifact()

    @abstractmethod
    def load(self, project_root: Path) -> DataFrame:
        pass

    @abstractmethod
    def get_paths(self, project_root: Path) -> List[Path]:
        pass

    def get_mapper(self) -> ArtifactMapper:
        return self.mapper

    def is_test_set(self):
        return self.test_set


@dataclass(frozen=True)
class Task:
    name: str
    top_artifact: Type
    labels: List[str]
    train_datasets: Dict[str, DatasetLoader]
    test_datasets: Dict[str, DatasetLoader]
    label_column_name: str
    project_root: Path

    @property
    def datasets(self) -> Dict[str, DatasetLoader]:
        return {**self.train_datasets, **self.test_datasets}

    def _datapaths(self, datasets: Iterable[DatasetLoader]) -> List[Path]:
        return [p for dataset in datasets for p in dataset.get_paths(self.project_root)]

    @property
    def datapaths(self) -> List[Path]:
        return self.train_datapaths + self.test_datapaths

    @property
    def train_datapaths(self) -> List[Path]:
        return self._datapaths(self.train_datasets.values())

    @property
    def test_datapaths(self) -> List[Path]:
        return self._datapaths(self.test_datasets.values())

    def __post_init__(self):
        for dataset in self.datasets.values():
            if dataset.get_artifact() != self.top_artifact:
                raise ValueError(
                    f"Dataset {dataset} is a dataset of {dataset.get_artifact()}, "
                    f"but this task works on {self.top_artifact}"
                )
