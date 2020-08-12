#!/bin/bash
#
# Weekly rebuild of llvm, cheribsd, and minimal kernels for testing

echo y | ./cheribuild.py llvm && \
echo y | ./cheribuild.py cheribsd-mips-purecap && \
echo y | ./cheribuild.py disk-image-minimal-mips-purecap && \
echo y | ./cheribuild.py cheribsd-mfs-root-kernel-mips-purecap --cheribsd-mfs-root-kernel/no-build-fpga-kernels && \
./cheribuild.py ros2-mips-purecap --test
