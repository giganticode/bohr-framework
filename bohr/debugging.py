import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from shutil import copy
from time import time
from typing import Dict, Optional, Tuple

import appdirs
import dvc.api
import git
import numpy as np
import pandas as pd
from git import Repo
from tabulate import tabulate

from bohr import appauthor, appname, version
from bohr.pathconfig import load_path_config

logger = logging.getLogger()


def _normalize_weights(x: np.ndarray) -> np.ndarray:
    """
    >>> _normalize_weights(np.array([[0.019144, 0.011664], [0.005839, 0.004232], [0.003673, 0.003746], [0.020836, 0.011061]]))
    array([[0.23081334, 0.05360646],
           [0.17752456, 0.04366187],
           [0.1628473 , 0.04270857],
           [0.23586317, 0.05297473]])
    >>> _normalize_weights(np.array([[0.71, 0.84], [0.84, 0.71]]))
    array([[0.16867129, 0.33132871],
           [0.33132871, 0.16867129]])
    """
    prod = np.exp(np.sum(np.log(x), axis=0))
    NBB = prod / np.sum(prod)
    x_modif = prod * np.log(prod) / np.log(x)
    norm_koef_x = NBB / np.sum(x_modif, axis=0)

    x_normalized = x_modif * norm_koef_x

    return x_normalized


def _load_output_matrix_and_weights(
    task_name: str,
    labeled_dataset: str,
    rev: Optional[str] = None,
    force_update: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    path_config = load_path_config()
    logging.disable(logging.WARNING)
    repo = (
        get_path_to_revision(path_config.project_root, rev, force_update=force_update)
        if rev is not None
        else None
    )
    with dvc.api.open(
        path_config.generated_dir
        / task_name
        / f"heuristic_matrix_{labeled_dataset}.pkl",
        repo,
        mode="rb",
    ) as f:
        matrix = pd.read_pickle(BytesIO(f.read()))

    with dvc.api.open(
        path_config.generated_dir / task_name / f"label_model_weights.csv", repo
    ) as f:
        weights = pd.read_csv(f, index_col="heuristic_name")
    logging.disable(logging.NOTSET)
    return matrix, weights


class DataPointDebugger:
    def __init__(
        self,
        task_name: str,
        labeled_dataset: str,
        rev: Optional[str] = "master",
        force_update: bool = False,
    ):
        self.dataset_debugger = DatasetDebugger(task_name, labeled_dataset, rev)
        self.old_matrix, self.old_weights = _load_output_matrix_and_weights(
            task_name, labeled_dataset, rev, force_update=force_update
        )
        self.new_matrix, self.new_weights = _load_output_matrix_and_weights(
            task_name, labeled_dataset
        )

    def get_datapoint_info_(
        self, matrix, weights, datapoint: int, suffix: str
    ) -> pd.DataFrame:
        row = matrix.iloc[datapoint]

        zero = f"NonBug_{suffix}"
        one = f"Bug_{suffix}"
        out = f"h_output_{suffix}"

        weights[out] = row
        weights = weights[weights[out] > -1]
        if weights.empty:
            print("No heuristic fired.")
            return pd.DataFrame([], columns=[zero, one, out])
        weights2 = weights.apply(
            lambda row: row[["00", "01"]].rename(({"00": zero, "01": one}))
            if row[out] == 0
            else row[["10", "11"]].rename(({"10": zero, "11": one})),
            axis=1,
        )
        weights2[[out]] = weights[[out]]
        weights2[[zero, one]] = pd.DataFrame(
            _normalize_weights(weights2[[zero, one]].to_numpy()), index=weights.index
        )
        return weights2

    def show_datapoint_info(self, datapoint: int) -> None:
        self.dataset_debugger.show_datapoint(datapoint)
        old = self.get_datapoint_info_(
            self.old_matrix, self.old_weights, datapoint, "old"
        )
        new = self.get_datapoint_info_(
            self.new_matrix, self.new_weights, datapoint, "new"
        )
        concat_df = pd.concat([old, new], axis=1)
        print(tabulate(concat_df, headers=concat_df.columns))

    def get_fired_heuristics_with_weights(self) -> Dict[str, float]:
        pass


def get_cloned_rev(repo: str, rev: str = "master") -> Repo:
    path = appdirs.user_cache_dir(
        appname=appname(), appauthor=appauthor(), version=version()
    )
    path_to_repo = Path(path) / repo / rev
    if not path_to_repo.exists():
        return Repo.clone_from(repo, path_to_repo, depth=1, b=rev)
    else:
        return Repo(path_to_repo)


def get_git_repo_of(path: Path) -> Repo:
    current_path = path
    while True:
        try:
            return Repo(current_path)
        except git.exc.InvalidGitRepositoryError:
            if current_path == current_path.parent:
                raise ValueError(f"Path {path} or its parents are not a git repo!")
            current_path = current_path.parent


def is_update_needed(git_revision: Repo) -> bool:
    fetch_head_file = Path(git_revision.working_tree_dir) / ".git" / "FETCH_HEAD"
    if not fetch_head_file.exists():
        return True

    last_modification = fetch_head_file.stat().st_mtime
    updated_sec_ago = time() - last_modification
    logger.debug(
        f"Repo {git_revision} last attempt to pull {datetime.fromtimestamp(last_modification)}"
    )
    return updated_sec_ago > 300


def update(repo: Repo, dvc_project_root: Path, rel_path_to_dvc_root: Path) -> None:
    logger.info("Updating the repo... ")
    repo.remotes.origin.pull()
    move_local_config_to_old_revision(
        dvc_project_root, repo.working_tree_dir / rel_path_to_dvc_root
    )


def move_local_config_to_old_revision(src: Path, dst: Path):
    config_path = Path(".dvc/config.local")
    logger.debug(f"Copying config from {src / config_path} to {dst / config_path}")
    copy(src / config_path, dst / config_path)


def get_path_to_revision(
    dvc_project_root: Path, rev: str, force_update: bool = False
) -> Path:
    current_repo = get_git_repo_of(dvc_project_root)
    remote = current_repo.remotes.origin
    old_revision: Repo = get_cloned_rev(remote.url, rev)
    rel_path_to_dvc_root = dvc_project_root.relative_to(current_repo.working_tree_dir)
    logger.info(
        f"Comparing to {remote.url} , revision: {rev}, \n"
        f"relative dvc root: {rel_path_to_dvc_root}\n"
        f"(Cloned to {old_revision.working_tree_dir})"
    )
    if is_update_needed(old_revision) or force_update:
        if force_update:
            logger.debug("Forcing refresh ...")
        update(old_revision, dvc_project_root, rel_path_to_dvc_root)
    else:
        logger.info(f"Pass `--force-refresh` to refresh the repository.")
    return old_revision.working_tree_dir / rel_path_to_dvc_root


class DatasetDebugger:
    def __init__(
        self,
        task: str,
        labeled_dataset_name: str,
        rev: Optional[str] = "master",
        force_update: bool = False,
    ):
        path_config = load_path_config()
        path_to_old_revision = get_path_to_revision(
            path_config.project_root, rev, force_update
        )
        self.labeled_dataset_name = labeled_dataset_name
        logging.disable(logging.WARNING)
        labeled_dataset_path = (
            path_config.labeled_data_dir / f"{labeled_dataset_name}.labeled.csv"
        )
        with dvc.api.open(labeled_dataset_path, path_to_old_revision) as f:
            old_df = pd.read_csv(f)
        with dvc.api.open(labeled_dataset_path) as f:
            new_df = pd.read_csv(f)
        logging.disable(logging.NOTSET)

        self.is_test_set = "bug" in old_df.columns

        old_df_columns = ["prob_CommitLabel.BugFix"]
        if self.is_test_set:
            old_df_columns.append("bug")
        self.combined_df = pd.concat(
            [
                old_df[old_df_columns],
                new_df["prob_CommitLabel.BugFix"].rename("prob_CommitLabel.BugFix_new"),
            ],
            axis=1,
        )
        if self.is_test_set:
            self.combined_df.loc[:, "improvement"] = (
                self.combined_df["prob_CommitLabel.BugFix_new"]
                - self.combined_df["prob_CommitLabel.BugFix"]
            ) * (self.combined_df["bug"] * 2 - 1)

        self.combined_df.loc[:, "certainty"] = (
            np.abs(self.combined_df["prob_CommitLabel.BugFix_new"] - 0.5) * 2
        )
        if self.is_test_set:
            self.combined_df.loc[:, "precision"] = 1 - np.abs(
                self.combined_df["prob_CommitLabel.BugFix_new"]
                - self.combined_df["bug"]
            )

        self.combined_df = pd.concat([self.combined_df, old_df["message"]], axis=1)
        if "url" in old_df.columns:
            self.combined_df["url"] = old_df["url"]

    def show_datapoints(
        self,
        value: str,
        n: Optional[int] = 10,
        reverse: bool = False,
    ) -> None:
        if not self.is_test_set and value in ["improvement", "precision"]:
            raise ValueError(
                f"Dataset {self.labeled_dataset_name} has no ground-truth labels. "
                f"Cannot calculate {value}"
            )

        self.combined_df.sort_values(by=value, inplace=True, ascending=reverse)
        df = self.combined_df.head(n)
        pd.options.mode.chained_assignment = None
        df.loc[:, "message"] = df["message"].str.wrap(70)
        print(
            tabulate(
                df,
                headers=df.columns,
                tablefmt="fancy_grid",
            )
        )

    def show_datapoint(self, n: int) -> None:
        a = self.combined_df.loc[n].to_frame()
        print(tabulate(a))

    def debug_datapoint(self, n: int):
        pass
