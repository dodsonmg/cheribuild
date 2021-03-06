#
# Copyright (c) 2020 Alex Richardson
#
# This software was developed by SRI International and the University of
# Cambridge Computer Laboratory (Department of Computer Science and
# Technology) under DARPA contract HR0011-18-C-0016 ("ECATS"), as part of the
# DARPA SSITH research programme.
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

from pathlib import Path

from ..project import (BuildType, CheriConfig, ComputedDefaultValue, CPUArchitecture, DefaultInstallDir, GitRepository,
                       MakeCommandKind, Project)
from ...config.compilation_targets import CompilationTargets
from ...utils import classproperty, commandline_to_str, OSInfo


def opensbi_install_dir(config: CheriConfig, project: "BuildOpenSBI", suffix: str):
    dir_name = project.crosscompile_target.generic_suffix.replace("baremetal-", "")
    return config.cheri_sdk_dir / ("opensbi" + project.build_dir_suffix) / dir_name


class BuildOpenSBI(Project):
    target = "opensbi"
    repository = GitRepository("https://github.com/CTSRD-CHERI/opensbi")
    default_install_dir = DefaultInstallDir.CUSTOM_INSTALL_DIR
    default_build_type = BuildType.RELWITHDEBINFO
    supported_architectures = [
        CompilationTargets.BAREMETAL_NEWLIB_RISCV64_HYBRID,
        CompilationTargets.BAREMETAL_NEWLIB_RISCV64,
        # Won't compile yet: CompilationTargets.BAREMETAL_NEWLIB_RISCV64_PURECAP
    ]
    make_kind = MakeCommandKind.GnuMake
    _always_add_suffixed_targets = True
    _default_install_dir_fn = ComputedDefaultValue(function=lambda c, p: opensbi_install_dir(c, p, ""),
                                                   as_string="$SDK_ROOT/opensbi/riscv{32,64}{-hybrid,-purecap,}")

    @classproperty
    def needs_sysroot(cls):
        return False  # we can build without a sysroot

    def __init__(self, config):
        super().__init__(config)
        self.add_required_system_tool("dtc", apt="device-tree-compiler", homebrew="dtc")
        if OSInfo.IS_MAC:
            self.add_required_system_tool("greadlink", homebrew="coreutils")
            self.make_args.set(READLINK="greadlink")

    def setup(self):
        super().setup()
        compflags = " " + commandline_to_str(self.target_info.essential_compiler_and_linker_flags)
        compflags += " -Qunused-arguments"  # -mstrict-align -no-pie
        self.make_args.set(
            O=self.buildDir,  # output dir
            I=self.installDir,  # install dir
            CROSS_COMPILE=str(self.sdk_bindir) + "/",
            CC=str(self.CC) + compflags,
            CXX=str(self.CXX) + compflags,
            CPP=str(self.CPP) + compflags,
            LD=self.target_info.linker,
            AR=self.sdk_bindir / "llvm-ar",
            OBJCOPY=self.sdk_bindir / "llvm-objcopy",
            LD_IS_LLD=True,
            FW_OPTIONS="0x2",  # Debug output enabled for now
            # FW_JUMP_ADDR= ## cheribsd start addr
            # FW_JUMP_FDT_ADDR= ## cheribsd fdt addr
            PLATFORM_RISCV_ABI=self.target_info.riscv_softfloat_abi,
            PLATFORM_RISCV_ISA=self.target_info.riscv_arch_string,
            PLATFORM_RISCV_XLEN=64,
        )
        if self.config.verbose:
            self.make_args.set(V=True)

    @property
    def all_platforms(self):
        platforms_dir = self.sourceDir / "platform"
        self.info(list(platforms_dir.glob("**/config.mk")))
        all_platforms = []
        for c in platforms_dir.glob("**/config.mk"):
            relpath = str(c.parent.relative_to(platforms_dir))
            if relpath != "template":
                all_platforms.append(relpath)
        if "generic" not in all_platforms:
            self.fatal("generic platform missing?")
        # return all_platforms

        return ["generic"]

    def compile(self, **kwargs):
        for platform in self.all_platforms:
            args = self.make_args.copy()
            args.set(PLATFORM=platform)
            self.run_make(parallel=False, cwd=self.sourceDir, options=args)

    def install(self, **kwargs):
        self.makedirs(self.installDir)
        for platform in self.all_platforms:
            args = self.make_args.copy()
            args.set(PLATFORM=platform)
            self.runMakeInstall(cwd=self.sourceDir, options=args)

    def _fw_jump_path(self) -> Path:
        # share/opensbi/lp64/generic/firmware//fw_payload.bin
        return self.installDir / "share/opensbi/{abi}/generic/firmware/fw_jump.elf".format(
            abi=self.target_info.riscv_softfloat_abi)

    @classmethod
    def get_nocap_instance(cls, caller, cpu_arch=CPUArchitecture.RISCV64) -> "BuildOpenSBI":
        assert cpu_arch == CPUArchitecture.RISCV64, "RISCV32 not supported yet"
        return cls.get_instance(caller, cross_target=CompilationTargets.BAREMETAL_NEWLIB_RISCV64)

    @classmethod
    def get_hybrid_instance(cls, caller, cpu_arch=CPUArchitecture.RISCV64) -> "BuildOpenSBI":
        assert cpu_arch == CPUArchitecture.RISCV64, "RISCV32 not supported yet"
        return cls.get_instance(caller, cross_target=CompilationTargets.BAREMETAL_NEWLIB_RISCV64_HYBRID)

    @classmethod
    def get_nocap_bios(cls, caller) -> Path:
        return cls.get_nocap_instance(caller)._fw_jump_path()

    @classmethod
    def get_cheri_bios(cls, caller):
        # We currently use a hybrid build for
        return cls.get_hybrid_instance(caller)._fw_jump_path()


class BuildOpenSBIGFE(BuildOpenSBI):
    target = "opensbi-gfe"
    project_name = "opensbi"
    build_dir_suffix = "-gfe"

    def setup(self):
        super().setup()
        self.make_args.set(FW_TEXT_START=0xc0000000)
