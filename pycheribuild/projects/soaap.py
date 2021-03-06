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
from .llvm import BuildLLVMSplitRepoBase
from .project import CMakeProject, GitRepository
from ..config.loader import ComputedDefaultValue

install_to_soaap_dir = ComputedDefaultValue(function=lambda config, project: config.outputRoot / "soaap",
                                            as_string="$INSTALL_ROOT/soaap")


class BuildSoaapLLVM(BuildLLVMSplitRepoBase):
    target = "soaap-llvm"
    project_name = "soaap-llvm"
    githubBaseUrl = "https://github.com/CTSRD-SOAAP/"
    repository = GitRepository(githubBaseUrl + "llvm.git")
    no_default_sysroot = True
    skip_misc_llvm_tools = False
    skip_static_analyzer = False
    _default_install_dir_fn = install_to_soaap_dir
    skip_cheri_symlinks = True

    @classmethod
    def setup_config_options(cls, **kwargs):
        cls.included_projects = ["llvm", "clang"]
        super().setup_config_options(include_lldb_revision=False, include_lld_revision=False, **kwargs)


class BuildSoaap(CMakeProject):
    dependencies = ["soaap-llvm"]
    repository = GitRepository("https://github.com/CTSRD-SOAAP/soaap")
    _default_install_dir_fn = install_to_soaap_dir

    def configure(self, **kwargs):
        soaap_llvm = BuildSoaapLLVM.get_instance(self)
        print(soaap_llvm.configureArgs)
        build_shared_libs = any(x == "-DBUILD_SHARED_LIBS=ON" for x in soaap_llvm.configureArgs)
        self.add_cmake_options(LLVM_DIR=soaap_llvm.buildDir / "share/llvm/cmake")
        self.add_cmake_options(BUILD_SHARED_LIBS=build_shared_libs)
        super().configure(**kwargs)

