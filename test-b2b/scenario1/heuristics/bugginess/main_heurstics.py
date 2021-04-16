import re
from typing import Optional

from labels import *

from bohr.artifacts.commit import Commit
from bohr.decorators import Heuristic
from bohr.labels.labelset import Label, Labels
from bohr.nlp_utils import NgramSet
from bohr.templates.heuristics.keywords import KeywordHeuristics


@KeywordHeuristics(Commit, "bug", name_pattern="bug_message_keyword_%1")
def bug_keywords_lookup_in_message(
    commit: Commit, keywords: NgramSet
) -> Optional[Labels]:
    if commit.message.match_ngrams(keywords):
        return CommitLabel.BugFix
    return None


@KeywordHeuristics(Commit, "bugless", name_pattern="bugless_message_keyword_%1")
def bugless_keywords_lookup_in_message(
    commit: Commit, keywords: NgramSet
) -> Optional[Labels]:
    if commit.message.match_ngrams(keywords):
        return CommitLabel.NonBugFix
    return None


# @keyword_labeling_functions('bogusbugs', name_pattern='bogusbugs_message_keyword_%1')
def bogus_fix_keyword_in_message(commit: Commit, keywords: NgramSet) -> Optional[Label]:
    if "fix" in commit.message.stemmed_ngrams or "bug" in commit.message.stemmed_ngrams:
        if commit.message.match_ngrams(keywords):
            return CommitLabel.NonBugFix
        else:
            return CommitLabel.BugFix
    return None


GITHUB_REF_RE = re.compile(r"gh(-|\s)\d+", flags=re.I)
VERSION_RE = re.compile(r"v\d+.*", flags=re.I)


@Heuristic(Commit)
def github_ref_in_message(commit: Commit) -> Optional[Labels]:
    return CommitLabel.BugFix if GITHUB_REF_RE.search(commit.message.raw) else None


@Heuristic(Commit)
def version_in_message(commit: Commit) -> Optional[Labels]:
    return CommitLabel.NonBugFix if VERSION_RE.search(commit.message.raw) else None


@KeywordHeuristics(Commit, "bug.issue_label", name_pattern="bug_issue_label_keyword_%1")
def bug_keywords_lookup_in_issue_label(
    commit: Commit, keywords: NgramSet
) -> Optional[Labels]:
    if commit.issues_match_label(keywords):
        return CommitLabel.BugFix
    return None


@KeywordHeuristics(
    Commit, "bugless.issue_label", name_pattern="bugless_issue_label_keyword_%1"
)
def bugless_keywords_lookup_in_issue_label(
    commit: Commit, keywords: NgramSet
) -> Optional[Labels]:
    if commit.issues_match_label(keywords):
        return CommitLabel.NonBugFix
    return None


@KeywordHeuristics(Commit, "bug", name_pattern="bug_issue_body_keyword_%1")
def bug_keywords_lookup_in_issue_body(
    commit: Commit, keywords: NgramSet
) -> Optional[Labels]:
    if commit.issues_match_ngrams(keywords):
        return CommitLabel.BugFix
    return None


@KeywordHeuristics(Commit, "bugless", name_pattern="bugless_issue_body_keyword_%1")
def bugless_keywords_lookup_in_issue_body(
    commit: Commit, keywords: NgramSet
) -> Optional[Labels]:
    if commit.issues_match_ngrams(keywords):
        return CommitLabel.NonBugFix
    return None


@Heuristic(Commit)
def no_files_have_modified_status(commit: Commit) -> Optional[Labels]:
    for file in commit.commit_files:
        if file.status == "modified":
            return None
    return CommitLabel.NonBugFix


@Heuristic(Commit)
def bug_if_only_changed_lines_in_one_file(commit: Commit) -> Optional[Labels]:
    if (
        len(commit.commit_files) == 1
        and commit.commit_files[0].status == "modified"
        and commit.commit_files[0].changes
        and commit.commit_files[0].no_added_lines()
        and commit.commit_files[0].no_removed_lines()
    ):
        return CommitLabel.BugFix
    return None


@Heuristic(Commit)
def bugless_if_many_files_changes(commit: Commit) -> Optional[Labels]:
    if len(commit.commit_files) > 6:
        return CommitLabel.NonBugFix
    else:
        return None
