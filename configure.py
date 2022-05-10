# Copyright 2020 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License .
# ==============================================================================
# Usage: python configure.py
#

import os
import pathlib
import platform
import logging

import tensorflow as tf

_TFRA_BAZELRC = ".bazelrc"


# Maping TensorFlow version to valid Bazel version.
def _VALID_BAZEL_VERSION(tf_version):
  if is_macos() and is_arm64():
    target_bazel = "4.1.0"
    logging.warn(
        'Only Bazel version greater than 4.1.0 supports macOS arm64 platform.')
    return target_bazel
  elif tf_version < "2.0.0":
    target_bazel = "0.26.1"
    logging.warn(
        'There is only limited support for TensorFlow under version 2.0.0 '
        'because its Bazel version, and requiring users to make some Bazel script changes '
        'refering to the previous COMMIT to compile properly by themselves.')
    return target_bazel
  elif tf_version >= "2.0.0":
    target_bazel = "4.2.1"
    logging.info(
        'To ensure code compatibility with Bazel rules_foreign_cc component, '
        'we specify Bazel version greater than 3.7.2 '
        'for Tensorflow versions greater than 2.0.0.')
    return target_bazel
  else:
    raise ValueError('Unsupport TensorFlow version {}.'.format(tf_version))


# Writes variables to bazelrc file
def write(line):
  with open(_TFRA_BAZELRC, "a") as f:
    f.write(line + "\n")


def write_action_env(var_name, var):
  write('build --action_env {}="{}"'.format(var_name, var))


def is_macos():
  return platform.system() == "Darwin"


def is_windows():
  return platform.system() == "Windows"


def is_linux():
  return platform.system() == "Linux"


def is_arm64():
  return platform.machine() == "arm64"


def is_raspi_arm():
  return os.uname()[4] == "armv7l"


def get_tf_header_dir():
  if get_tf_version_integer() >= 2000:
    tf_header_dir = tf.sysconfig.get_compile_flags()[0][2:]
    if is_windows():
      tf_header_dir = tf_header_dir.replace("\\", "/")
  else:
    current_path = os.path.dirname(os.path.abspath(__file__))
    tf_header_dir = "{}/build_deps/tf_header/{}/tensorflow".format(
        current_path, tf.__version__)
  return tf_header_dir


def get_tf_shared_lib_dir():
  # OS Specific parsing
  if is_windows():
    tf_shared_lib_dir = tf.sysconfig.get_compile_flags()[0][2:-7] + "python"
    return tf_shared_lib_dir.replace("\\", "/")
  elif is_raspi_arm():
    return tf.sysconfig.get_compile_flags()[0][2:-7] + "python"
  else:
    return tf.sysconfig.get_link_flags()[0][2:]


# Converts the linkflag namespec to the full shared library name
def get_shared_lib_name():
  namespec = tf.sysconfig.get_link_flags()
  if is_macos():
    # MacOS
    return "libtensorflow_framework.dylib"
  elif is_windows():
    # Windows
    return "_pywrap_tensorflow_internal.lib"
  elif is_raspi_arm():
    # The below command for linux would return an empty list
    return "_pywrap_tensorflow_internal.so"
  else:
    # Linux
    return namespec[1][3:]


def get_tf_version_integer():
  """
  Get Tensorflow version as a 4 digits string.

  For example:
    1.15.2 get 1152
    2.4.1 get 2041
    2.5.1 get 2051

  The 4-digits-string will be passed to C macro to discriminate different
  Tensorflow versions. 

  We assume that major version has 1 digit, minor version has 2 digits. And
  patch version has 1 digit.
  """
  try:
    version = tf.__version__
  except AttributeError:
    raise ImportError(
        '\nPlease install a TensorFlow on your compiling machine, '
        'The compiler needs to know the version of Tensorflow '
        'and get TF c++ headers according to the installed TensorFlow. '
        '\nNote: Only TensorFlow 2.7.0, 2.5.1, 2.4.1, 1.15.2 are supported.')
  try:
    major, minor, patch = version.split('.')
    assert len(
        major
    ) == 1, "Tensorflow major version must be length of 1. Version: {}".format(
        version)
    assert len(
        minor
    ) <= 2, "Tensorflow minor version must be less or equal to 2. Version: {}".format(
        version)
    assert len(
        patch
    ) == 1, "Tensorflow patch version must be length of 1. Version: {}".format(
        version)
  except:
    raise ValueError('got wrong tf.__version__: {}'.format(version))
  tf_version_num = str(int(major) * 1000 + int(minor) * 10 + int(patch))
  if len(tf_version_num) != 4:
    raise ValueError('Tensorflow version flag must be length of 4 (major'
                     ' version: 1, minor version: 2, patch_version: 1). But'
                     ' get: {}'.format(tf_version_num))
  return int(tf_version_num)


def _get_installed_and_valid_bazel_version():
  stream = os.popen('bazel version |grep label')
  output = stream.read()
  installed_bazel_version = str(output).split(":")[1].strip()
  valid_bazel_version = _VALID_BAZEL_VERSION(tf.__version__)
  return installed_bazel_version, valid_bazel_version


def check_bazel_version():
  installed_bazel_version, valid_bazel_version = _get_installed_and_valid_bazel_version(
  )
  if installed_bazel_version != valid_bazel_version:
    raise ValueError('Bazel version is {}, but {} is needed.'.format(
        installed_bazel_version, valid_bazel_version))


def check_bazel_version_for_macOS_arm64():
  installed_bazel_version, valid_bazel_version = _get_installed_and_valid_bazel_version(
  )
  if installed_bazel_version < valid_bazel_version:
    raise ValueError(
        'Bazel version is {}. For macOS arm64 platform, Bazel version must be at least {}.'
        .format(installed_bazel_version, valid_bazel_version))


def extract_tf_header():
  tf_header_dir = get_tf_header_dir()
  tf_version_integer = get_tf_version_integer()
  if tf_version_integer < 2000:
    _output_dir = tf_header_dir[:-(len(tf.__version__ + "/tensorflow"))]
    _tar_path = tf_header_dir.replace("/tensorflow", ".tar.gz")
    _cmd = "tar -zxvf {} --directory {} >/dev/null 2>&1".format(
        _tar_path, _output_dir)
    ret = os.system(_cmd)
    if ret != 0:
      raise ValueError(
          'Error happened when decompressing TF headers tar file:{}.'.format(
              _tar_path))


def create_build_configuration():
  print()
  print("Configuring TensorFlow Recommenders-Addons to be built from source...")

  if os.path.isfile(_TFRA_BAZELRC):
    os.remove(_TFRA_BAZELRC)
  if is_linux():
    check_bazel_version()
  if is_macos() and is_arm64():
    check_bazel_version_for_macOS_arm64()
  extract_tf_header()
  logging.disable(logging.WARNING)

  write_action_env("TF_HEADER_DIR", get_tf_header_dir())
  write_action_env("TF_SHARED_LIBRARY_DIR", get_tf_shared_lib_dir())
  write_action_env("TF_SHARED_LIBRARY_NAME", get_shared_lib_name())
  write_action_env("TF_CXX11_ABI_FLAG", tf.sysconfig.CXX11_ABI_FLAG)

  tf_version_integer = get_tf_version_integer()
  # This is used to trace the difference between Tensorflow versions.
  write_action_env("TF_VERSION_INTEGER", tf_version_integer)

  write_action_env("FOR_TF_SERVING", os.getenv("FOR_TF_SERVING", "0"))

  write("build --spawn_strategy=standalone")
  write("build --strategy=Genrule=standalone")
  write("build -c opt")

  if is_windows():
    write("build --config=windows")
    write("build:windows --enable_runfiles")
    write("build:windows --copt=/experimental:preprocessor")
    write("build:windows --host_copt=/experimental:preprocessor")
    write("build:windows --copt=/arch=AVX")

  if is_macos() or is_linux():
    if not is_arm64():
      write("build --copt=-mavx")

  if os.getenv("TF_NEED_CUDA", "0") == "1":
    print("> Building CUDA GPU & CPU ops")
    configure_cuda()
  elif os.getenv("TF_NEED_ROCM", "0") == "1":
    print("> Building ROCM GPU & CPU ops")
    configure_rocm()
  else:
    print("> Building only CPU ops")

  print()
  print("Build configurations successfully written to", _TFRA_BAZELRC, ":\n")
  print(pathlib.Path(_TFRA_BAZELRC).read_text())


def configure_cuda():
  write_action_env("TF_NEED_CUDA", "1")
  write_action_env("CUDA_TOOLKIT_PATH",
                   os.getenv("CUDA_TOOLKIT_PATH", "/usr/local/cuda"))
  write_action_env(
      "CUDNN_INSTALL_PATH",
      os.getenv("CUDNN_INSTALL_PATH", "/usr/lib/x86_64-linux-gnu"),
  )
  write_action_env("TF_CUDA_VERSION", os.getenv("TF_CUDA_VERSION", "11.0"))
  write_action_env("TF_CUDNN_VERSION", os.getenv("TF_CUDNN_VERSION", "8.0"))

  write("test --config=cuda")
  write("build --config=cuda")
  write("build:cuda --define=using_cuda=true --define=using_cuda_nvcc=true")
  write("build:cuda --crosstool_top=@local_config_cuda//crosstool:toolchain")


def configure_rocm():
  write_action_env("TF_NEED_ROCM", "1")
  write_action_env("ROCM_PATH",
                   os.getenv("ROCM_PATH", "/opt/rocm"))

  write("test --config=rocm")
  write("build --config=rocm")
  write("build:rocm --define=using_rocm_hipcc=true")
  write("build:rocm --define=tensorflow_mkldnn_contraction_kernel=0")
  write("build:rocm --repo_env TF_NEED_ROCM=1")
  write("build:rocm --crosstool_top=@local_config_rocm//crosstool:toolchain")


if __name__ == "__main__":
  create_build_configuration()
