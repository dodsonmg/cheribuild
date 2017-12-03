#
# Copyright (c) 2016 Alex Richardson
# All rights reserved.
#
# This software was developed by SRI International and the University of
# Cambridge Computer Laboratory under DARPA/AFRL contract FA8750-10-C-0237
# ("CTSRD"), as part of the DARPA CRASH research programme.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
import functools
import sys
import time

from .config.chericonfig import CheriConfig
from .utils import *


class Target(object):
    def __init__(self, name, projectClass, *, dependencies: set=set()):
        self.name = name
        self.dependencies = set(dependencies)
        self.projectClass = projectClass
        self.project = None  # type: pycheribuild.project.SimpleProject
        self._completed = False

    def checkSystemDeps(self, config: CheriConfig):
        if self._completed:
            return
        self.project = self.projectClass(config)
        with setEnv(PATH=self.project.config.dollarPathWithOtherTools):
            # make sure all system dependencies exist first
            self.project.checkSystemDependencies()

    def execute(self):
        if self._completed:
            # TODO: make this an error once I have a clean solution for the pseudo targets
            warningMessage(self.name, "has already been executed!")
            return
        # instantiate the project and run it
        starttime = time.time()
        with setEnv(PATH=self.project.config.dollarPathWithOtherTools):
            self.project.process()
        statusUpdate("Built target '" + self.name + "' in", time.time() - starttime, "seconds")
        self._completed = True

    def __lt__(self, other: "Target"):
        # print(self, "__lt__", other)
        # if this target is one of the dependencies order it before
        otherDeps = other.projectClass.allDependencyNames()
        # print("other deps:", otherDeps)
        if self.name in otherDeps:
            # print(self, "is in", other, "deps -> is less")
            return True
        if other.name.startswith("run") and not self.name.startswith("run"):
            return True  # run must be executed last
        elif self.name.startswith("run"):
            return False
        if other.name.startswith("disk-image") and not self.name.startswith("disk-image"):
            return True  # disk-image should be done just before run
        elif self.name.startswith("disk-image"):
            return False
        # print(self, "is not in", other, "deps -> is not less")
        # otherwise just keep everything in order
        return False
        # This was previously done
        # ownDeps = self.projectClass.allDependencyNames()
        # if len(ownDeps) < len(otherDeps):
        #     return True
        # if len(ownDeps) > len(otherDeps):
        #     return False
        # return self.name < other.name  # not a dep and number of deps is the same -> compare name

    def __repr__(self):
        return "<Target " + self.name + ">"


class TargetManager(object):
    def __init__(self):
        self._allTargets = {}

    def addTarget(self, target: Target):
        self._allTargets[target.name] = target

    def registerCommandLineOptions(self):
        # this cannot be done in the Project metaclass as otherwise we get
        # RuntimeError: super(): empty __class__ cell
        # https://stackoverflow.com/questions/13126727/how-is-super-in-python-3-implemented/28605694#28605694
        for tgt in self._allTargets.values():
            tgt.projectClass.setupConfigOptions()

    @property
    def targetNames(self):
        return self._allTargets.keys()

    @property
    def targetMap(self) -> "typing.Dict[str, Target]":
        return self._allTargets.copy()

    def topologicalSort(self, targets: "typing.List[Target]") -> "typing.Iterable[typing.List[Target]]":
        # based on http://rosettacode.org/wiki/Topological_sort#Python
        data = dict((t.name, set(t.dependencies)) for t in targets)

        # add all the targets that aren't included yet
        allDependencyNames = [t.projectClass.allDependencyNames() for t in targets]
        possiblyMissingDependencies = functools.reduce(set.union, allDependencyNames, set())
        for dep in possiblyMissingDependencies:
            if dep not in data:
                data[dep] = self.targetMap[dep].dependencies

        # do the actual sorting
        while True:
            ordered = set(item for item, dep in data.items() if not dep)
            if not ordered:
                break
            yield list(sorted(ordered))
            data = {item: (dep - ordered) for item, dep in data.items()
                    if item not in ordered}
        assert not data, "A cyclic dependency exists amongst %r" % data

    @staticmethod
    def sort_in_dependency_order(targets: "typing.List[Target]") -> "typing.List[Target]":
        result = []
        while targets:
            lowest = targets[0]
            # find the target that orders lower than any other target in the list (see Target.__lt__)
            # This means it doesn't depend on any of the other targets
            for t in targets[1:]:
                # print(t.name, "<", lowest.name, "=", t < lowest)
                if t < lowest:
                    lowest = t
            # skip duplicates that got inserted due to dependency adding
            if lowest not in result:
                result.append(lowest)
            targets.remove(lowest)
        return result

    def get_all_targets(self, explicit_targets: "typing.List[Target]", add_dependencies: bool) -> "typing.List[Target]":
        chosen_targets = []
        for t in explicit_targets:
            chosen_targets.append(t)
            deps_to_add = []
            if add_dependencies:
                deps_to_add = t.projectClass.allDependencyNames()
            elif t.projectClass.dependenciesMustBeBuilt:
                    # some targets such as sdk always need their dependencies build:
                    deps_to_add = t.projectClass.allDependencyNames()
            elif t.projectClass.isAlias:
                assert not t.projectClass.dependenciesMustBeBuilt
                # for aliases without full dependencies just add the direct dependencies
                deps_to_add = t.projectClass.dependencies
            chosen_targets.extend(self.targetMap[dep] for dep in deps_to_add)

        return self.sort_in_dependency_order(chosen_targets)

    def run(self, config: CheriConfig):
        # check that all target dependencies are correct:
        for t in self._allTargets.values():
            for dep in t.dependencies:
                if dep not in self._allTargets:
                    sys.exit("Invalid dependency " + dep + " for " + t.projectClass.__name__)

        # targetsSorted = sorted(self._allTargets.values())
        # print(" ".join(t.name for t in targetsSorted))
        # assert self._allTargets["llvm"] < self._allTargets["cheribsd"]
        # assert self._allTargets["llvm"] < self._allTargets["all"]
        # assert self._allTargets["disk-image"] > self._allTargets["qemu"]
        # assert self._allTargets["sdk"] > self._allTargets["sdk-sysroot"]

        explicitlyChosenTargets = []  # type: typing.List[Target]
        for targetName in config.targets:
            if targetName not in self._allTargets:
                sys.exit(coloured(AnsiColour.red, "Target", targetName, "does not exist. Valid choices are",
                                  ",".join(self.targetNames)))
            explicitlyChosenTargets.append(self.targetMap[targetName])

        chosenTargets = self.get_all_targets(explicitlyChosenTargets, config.includeDependencies)
        if config.verbose:
            print("Will execute the following targets:", " ".join(t.name for t in chosenTargets))
        # now that the chosen targets have been resolved run them
        for target in chosenTargets:
            target.checkSystemDeps(config)
        # all dependencies exist -> run the targets
        for target in chosenTargets:
            target.execute()

targetManager = TargetManager()
