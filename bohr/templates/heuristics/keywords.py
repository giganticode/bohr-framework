from pathlib import Path
from typing import Callable, List, Type

from bohr import datamodel
from bohr.artifacts.core import Artifact
from bohr.config import load_config
from bohr.core import KEYWORD_GROUP_SEPARATOR
from bohr.decorators import Heuristic
from bohr.labels.labelset import Label
from bohr.pathconfig import load_path_config


class KeywordHeuristics(Heuristic):
    def __init__(
        self,
        artifact_type_applied_to: Type[Artifact],
        keyword_list_name: str,
        name_pattern: str,
        resources=None,
    ):
        super().__init__(artifact_type_applied_to)
        self.keyword_list_name = keyword_list_name
        self.name_pattern = name_pattern
        self.resources = resources

    def __call__(self, f: Callable[..., Label]) -> List[datamodel.Heuristic]:

        heuristic_list = []
        path_config = load_path_config()
        file = path_config.heuristics / "keywords" / f"{self.keyword_list_name}.kwords"
        keyword_list = load_keywords_from_file(file)
        for keyword_group in keyword_list:

            def to_tuple_or_str(lst: List[str]):
                return lst[0] if len(lst) == 1 else tuple(lst)

            keywords = {to_tuple_or_str(kw.split(" ")) for kw in keyword_group}
            first_keyword = sorted(keywords, key=lambda x: " ".join(x))[0]
            name_elem = (
                first_keyword
                if isinstance(first_keyword, str)
                else "|".join(first_keyword)
            )
            name = self.name_pattern.replace("%1", name_elem)
            resources = dict(keywords=keyword_group)

            safe_func = self.get_artifact_safe_func(f)
            safe_func.__name__ = name
            heuristic = datamodel.Heuristic(
                safe_func,
                artifact_type_applied_to=self.artifact_type_applied_to,
                resources=resources,
            )

            heuristic_list.append(heuristic)
        return heuristic_list


def load_keywords_from_file(path: Path) -> List[List[str]]:
    with open(path) as f:
        lines = f.readlines()
        return [line.rstrip("\n").split(KEYWORD_GROUP_SEPARATOR) for line in lines]
