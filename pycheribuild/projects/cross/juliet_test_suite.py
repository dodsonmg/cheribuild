#
# Copyright (c) 2017 Alex Richardson
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

from .crosscompileproject import *
from ..project import ReuseOtherProjectRepository


class BuildJulietTestSuite(CrossCompileCMakeProject):
    project_name = "juliet-test-suite"
    # TODO: move repo to CTSRD-CHERI
    repository = GitRepository("https://github.com/arichardson/juliet-test-suite-c.git")
    crossInstallDir = CrossInstallDir.CHERIBSD_ROOTFS
    appendCheriBitsToBuildDir = True
    supported_architectures = [CompilationTargets.CHERIBSD_MIPS_PURECAP, CompilationTargets.NATIVE, CompilationTargets.CHERIBSD_MIPS]
    defaultOptimizationLevel = ["-O0"]
    default_build_type = BuildType.DEBUG

    @classmethod
    def setup_config_options(cls, **kwargs):
        super().setup_config_options(**kwargs)

    def process(self):
        if self.cross_build_type != BuildType.DEBUG:
            self.warning("The Juliet test suite contains undefined behaviour that might be optimized away unless you compile"
                         " at -O0.")
            self.ask_for_confirmation("Are you sure you want to continue?")
        super().process()

    def configure(self, **kwargs):
        pass

    def install(*args, **kwargs):
        pass

    def run_tests(self):
        pass


class BuildJulietCWESubdir(CrossCompileCMakeProject):
    doNotAddToTargets = True
    cwe_number = None

    @classmethod
    def setup_config_options(cls, **kwargs):
        super().setup_config_options(**kwargs)
        cls.testcase_timeout = cls.add_config_option("testcase-timeout", kind=str)
        cls.ld_preload_path = cls.add_config_option("ld-preload-path", kind=str)

    def configure(self, **kwargs):
        self.add_cmake_options(PLACE_OUTPUT_IN_TOPLEVEL_DIR=False)
        self.createSymlink(self.sourceDir / "../../CMakeLists.txt", self.sourceDir / "CMakeLists.txt")
        super().configure(**kwargs)

    def install(self, **kwargs):
        self.info("No need to install!")
        pass

    def run_tests(self):
        args = []
        if self.testcase_timeout:
            args.append("--testcase-timeout")
            args.append(self.testcase_timeout)
        if self.ld_preload_path:
            args.append("--ld-preload-path")
            args.append(self.ld_preload_path)

        self.run_cheribsd_test_script("run_juliet_tests.py", *args, mount_sourcedir=True, mount_sysroot=True, mount_builddir=True)

class BuildJulietCWE121(BuildJulietCWESubdir):
    project_name = "juliet-cwe-121"
    cwe_number = 121
    repository = ReuseOtherProjectRepository(BuildJulietTestSuite, subdirectory="testcases/CWE121_Stack_Based_Buffer_Overflow")

class BuildJulietCWE126(BuildJulietCWESubdir):
    project_name = "juliet-cwe-126"
    cwe_number = 126
    repository = ReuseOtherProjectRepository(BuildJulietTestSuite, subdirectory="testcases/CWE126_Buffer_Overread")

class BuildJulietCWE415(BuildJulietCWESubdir):
    project_name = "juliet-cwe-415"
    cwe_number = 415
    repository = ReuseOtherProjectRepository(BuildJulietTestSuite, subdirectory="testcases/CWE415_Double_Free")

class BuildJulietCWE416(BuildJulietCWESubdir):
    project_name = "juliet-cwe-416"
    cwe_number = 416
    repository = ReuseOtherProjectRepository(BuildJulietTestSuite, subdirectory="testcases/CWE416_Use_After_Free")
