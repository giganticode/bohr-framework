import logging
import re
import subprocess
from abc import ABC
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from bohr.config import Config, load_config
from bohr.datamodel import Task

logger = logging.getLogger(__name__)


class DvcCommand(ABC):
    def __init__(self, template: str, config: Config, task: Task):
        self.template = template
        self.config = config
        self.task = task

    def render_stage_template(self, template) -> str:
        return template.render(task=self.task, config=self.config)

    def to_string(self) -> List[str]:
        env = Environment(
            loader=FileSystemLoader(Path(__file__).parent.parent),
            undefined=StrictUndefined,
        )
        template = env.get_template(f"resources/dvc_command_templates/{self.template}")
        command = self.render_stage_template(template)
        command = f"dvc run -f --no-exec --force {command}"
        command_array = list(filter(None, re.split("[\n ]", command)))
        return command_array

    def run(self) -> None:
        command = self.to_string()
        logger.debug(f"Running {command}")
        subprocess.run(command, cwd=self.config.project_root)


class ApplyHeuristicsCommand(DvcCommand):
    def __init__(self, config: Config, task: Task, heuristic_group: str, dataset: str):
        super().__init__("apply_heuristics.template", config, task)
        self.heuristic_group = heuristic_group
        self.dataset = dataset

    def render_stage_template(self, template) -> str:
        return template.render(
            task=self.task,
            config=self.config,
            heuristic_group=self.heuristic_group,
            dataset=self.dataset,
        )


class CombineHeuristicsCommand(DvcCommand):
    def __init__(self, config: Config, task: Task):
        super().__init__("combine_heuristics.template", config, task)


class TrainLabelModelCommand(DvcCommand):
    def __init__(self, config: Config, task: Task):
        super().__init__("train_label_model.template", config, task)

    def render_stage_template(self, template) -> str:
        return template.render(
            task=self.task,
            config=self.config,
            target_dataset=next(iter(self.task.train_datasets.keys())),
        )


class LabelDatasetCommand(DvcCommand):
    def __init__(self, config: Config, task: Task, dataset: str):
        super().__init__("label_dataset.template", config, task)
        self.dataset = dataset

    def render_stage_template(self, template) -> str:
        return template.render(task=self.task, config=self.config, dataset=self.dataset)


def create_directories_if_necessary(config: Config) -> None:
    for task in config.tasks.values():
        for heuristic_group in task.heuristic_groups:
            (config.paths.generated / task.name / heuristic_group).mkdir(
                exist_ok=True, parents=True
            )
            (config.paths.metrics / task.name / heuristic_group).mkdir(
                exist_ok=True, parents=True
            )
    config.paths.labeled_data.mkdir(exist_ok=True, parents=True)


def add_all_tasks_to_dvc_pipeline(config: Config) -> None:
    create_directories_if_necessary(config)
    all_tasks = sorted(config.tasks.values(), key=lambda x: x.name)
    logger.info(
        f"Following tasks are added to the pipeline: {list(map(lambda x: x.name, all_tasks))}"
    )
    commands = []
    for task in all_tasks:
        for heuristic_group in task.heuristic_groups:
            for dataset_name in task.datasets:
                commands.append(
                    ApplyHeuristicsCommand(config, task, heuristic_group, dataset_name)
                )
        commands.append(CombineHeuristicsCommand(config, task))
        commands.append(TrainLabelModelCommand(config, task))
        for dataset_name in task.datasets:
            commands.append(LabelDatasetCommand(config, task, dataset_name))
    for command in commands:
        command.run()


if __name__ == "__main__":
    config = load_config()

    add_all_tasks_to_dvc_pipeline(config)
