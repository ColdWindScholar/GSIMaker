#!/bin/env python3
r"""
  __  __ ___ ____ ___ ____  _____
 |  \/  |_ _/ ___|_ _|  _ \| ____|
 | |\/| || |\___ \| || | | |  _|
 | |  | || | ___) | || |_| | |___
 |_|  |_|___|____/___|____/|_____|
       Love & You
"""
import os
import platform
import subprocess
import sys
import zipfile
from shutil import rmtree, move, copy, which

from src import imgextractor, ozipdecrypt
from src.contextpatch import main as contextpatch
from src.downloader import download
from src.fspatch import main as fspatch
from src.gettype import gettype
from src.payload_extract import extract_partitions_from_payload
from src.posix import readlink, symlink
from src.sdat2img import Sdat2img

if os.name == 'nt':
    import ctypes

    ctypes.windll.kernel32.SetConsoleTitleW("OEM Generic System Image Maker")
else:
    sys.stdout.write("\x1b]2;OEM Generic System Image Maker\x07")
    sys.stdout.flush()
__author__ = ["ColdWindScholar", "Child I"]
__version__ = "1.0.1"
if os.name == 'nt':
    prog_path = os.getcwd()
else:
    prog_path = os.path.normpath(os.path.abspath(os.path.dirname(sys.argv[0])))
    if platform.system() == 'Darwin':
        path_frags = prog_path.split(os.path.sep)
        if path_frags[-3:] == ['tool.app', 'Contents', 'MacOS']:
            path_frags = path_frags[:-3]
            prog_path = os.path.sep.join(path_frags)

IMG_DIR = os.path.join(prog_path, 'IMG')
EXTRACT_DIR = os.path.join(prog_path, 'EXTRACT')
tool_bin = os.path.join(prog_path, 'bin', platform.system(), platform.machine())
BIN_DIR = os.path.join(prog_path, 'bin')
img_files_list = ['my_bigball', 'my_carrier', 'my_engineering', 'my_heytap', 'my_manifest', 'my_product',
                  'my_region', 'my_stock', 'product', 'system', 'system_ext', 'mi_ext', 'vendor']


def call(exe, extra_path=True, out_=None) -> int:
    if not out_:
        out_ = True

    def output(inp: subprocess.CalledProcessError | subprocess.Popen[bytes]):
        for i in iter(inp.stdout.readline, b""):
            try:
                out_put = i.decode("utf-8").strip()
            except (Exception, BaseException):
                out_put = i.decode("gbk").strip()
            if out_:
                print(out_put)

    if isinstance(exe, list):
        cmd = exe
        if extra_path:
            cmd[0] = f"{tool_bin}/{exe[0]}"
        cmd = [i for i in cmd if i]
    else:
        cmd = f'{tool_bin}/{exe}' if extra_path else exe
        if os.name == 'posix':
            cmd = cmd.split()
    conf = subprocess.CREATE_NO_WINDOW if os.name != 'posix' else 0
    try:
        ret = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, creationflags=conf)
        output(ret)
    except subprocess.CalledProcessError as e:
        output(e)
        return 2
    except FileNotFoundError:
        return 2
    ret.wait()
    return ret.returncode


def check_tools():
    print("Checking necessary tools...")
    if not os.path.exists(tool_bin):
        print(f"BIN_DIR {tool_bin} not found.")
        return 1
    print("Done.")
    return 0


def select_file():
    projects = {}
    pro = 0
    print("Select file...")
    for pros in os.listdir(prog_path):
        if pros in ['bin', 'src'] or pros.startswith('.'):
            continue
        if os.path.isfile(os.path.join(prog_path, pros)) and pros.endswith('.zip'):
            pro += 1
            print(f"[{pro}]  {pros}\n")
            projects[str(pro)] = pros
    choice = input("Select project: ")
    if not choice or not choice in projects:
        return ""
    return projects[choice]


def extract_rom(path: str):
    if gettype(path) == 'ozip':
        ozipdecrypt.main(path)
        decrypted = os.path.dirname(path) + os.sep + os.path.basename(path)[:-4] + "zip"
        path = decrypted
    if not zipfile.is_zipfile(path):
        print(f"[{path}] is not a ZIP file")
        return 1
    with zipfile.ZipFile(path) as zip_file:
        if "payload.bin" in zip_file.namelist():
            print(f"正在从 {path} 提取 payload.bin...")
            zip_file.extract("payload.bin", EXTRACT_DIR)
        else:
            print(f"正在从 {path} 提取文件...")
            zip_file.extractall(EXTRACT_DIR)
    return 0


def extract_images():
    print("正在从 payload.bin 提取指定的img文件...")

    if os.path.exists(os.path.join(EXTRACT_DIR, 'payload.bin')):
        with open(os.path.join(EXTRACT_DIR, 'payload.bin'), "rb") as f:
            extract_partitions_from_payload(f, img_files_list, EXTRACT_DIR, os.cpu_count() or 2)
    else:
        for partition in img_files_list:
            if os.path.exists(os.path.join(EXTRACT_DIR, f"{partition}.new.dat.br")):
                if call(["brotli", "-d", f"{EXTRACT_DIR}/{partition}.new.dat.br"]): return 1
            if os.path.exists(os.path.join(EXTRACT_DIR, f"{partition}.new.dat.1")):
                with open(os.path.join(EXTRACT_DIR, f"{partition}.new.dat"), 'wb') as f:
                    for i in range(1000):
                        if os.path.exists(os.path.join(EXTRACT_DIR, f"{partition}.new.dat.{i}")):
                            with open(os.path.join(EXTRACT_DIR, f"{partition}.new.dat.{i}"), "rb") as split_dat:
                                f.write(split_dat.read())
            if os.path.exists(os.path.join(EXTRACT_DIR, f"{partition}.new.dat")):
                Sdat2img(os.path.join(EXTRACT_DIR, f"{partition}.transfer.list"),
                         os.path.join(EXTRACT_DIR, f"{partition}.new.dat"),
                         os.path.join(EXTRACT_DIR, f"{partition}.img"))
    print("Checking extracted images...：")
    extracted_count = 0
    for img in img_files_list:
        if os.path.exists(os.path.join(EXTRACT_DIR, f"{img}.img")):
            print(f"✓ {img}")
            extracted_count += 1
        else:
            print(f"✗ {img} (Not Found)")
    print(f"{extracted_count} Images extracted.")
    return 0


def decompose_images():
    print("正在分解提取的img文件...")
    for name in img_files_list:
        img_path = os.path.join(EXTRACT_DIR, f"{name}.img")
        if os.path.exists(img_path):
            print(f"Processing {name}...")
            file_type = gettype(img_path)
            if file_type == 'sparse':
                if call(["simg2img", f"{img_path}", f"{EXTRACT_DIR}/{name}_unsparse.img"]): return 1
                os.remove(img_path)
                os.rename(f"{EXTRACT_DIR}/{name}_unsparse.img", img_path)
            if file_type == 'ext':
                imgextractor.Extractor().main(img_path, f'{IMG_DIR}/{name}', IMG_DIR)
            if file_type == 'erofs':
                if call(["extract.erofs", "-i", f"{img_path}", "-o", f"{IMG_DIR}", "-x"], out_=False): return 1
            if not os.path.exists(f'{IMG_DIR}/{name}'):
                print(f"{name} 未能成功分解或分解目录为空。可能需要手动处理或使用其他工具。")
                return 1
            else:
                print(f"{name}[{file_type}]分解成功到{IMG_DIR}/{name}")
    return 0


def rm_rf(path: str):
    if os.name == 'posix':
        if readlink(path):
            os.remove(path)
    if not os.path.exists(path):
        return
    if os.path.isfile(path) or readlink(path):
        os.remove(path)
    if os.path.isdir(path):
        rmtree(path)


def get_prop(file: str, name: str) -> str:
    if os.path.isfile(file):
        with open(file, "r", encoding='utf-8') as f:
            for i in f.readlines():
                if i.startswith(f"{name}="):
                    _, value = i.split("=", 1)
                    return value.strip()
    return ""


def replace(file: str, origin: str, repl: str) -> int:
    with open(file, "r+", encoding='utf-8') as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        for i in lines:
            if i == origin:
                f.write(repl)
            else:
                f.write(i)
    return 0


def modify_parts() -> int:
    pass

def generate_markdown(mark_down_file: str):
    if not os.path.exists(os.path.dirname(mark_down_file)):
        os.makedirs(os.path.dirname(mark_down_file), exist_ok=True)
    build_file = f"{IMG_DIR}/system/system/build.prop"
    build_file_vendor = f"{IMG_DIR}/vendor/build.prop"
    vndk = get_prop(build_file, "ro.system.build.version.sdk")
    manufacturer = get_prop(build_file, "ro.product.system.manufacturer")
    is_hyper_os = get_prop(build_file, "ro.build.version.incremental")
    oem_os_dict = {
        "Xiaomi":"MIUI","meizu":"Flyme","vivo":"OriginOS","BLUEFOX":"FoxOS"
    }
    with open(mark_down_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f"## {f"HyperOS{is_hyper_os[2:]}" if is_hyper_os.startswith('OS') else oem_os_dict.get(manufacturer, manufacturer + "OS")}\n")
        f.write(f"## Ported from {get_prop(build_file, 'ro.product.system.model')}({get_prop(build_file, 'ro.product.system.device')})\n")
        f.write('\n')
        f.write('## Info\n')
        f.write("```\n")
        f.write(f"Device brand: {get_prop(build_file, 'ro.product.system.brand')}\n")
        f.write(f"Device manufacturer: {manufacturer}\n")
        f.write(f"Device model: {get_prop(build_file, 'ro.product.system.model')}\n")
        f.write(f"Device codename: {get_prop(build_file, 'ro.product.system.device')}\n")
        f.write(f"Device board: {get_prop(build_file_vendor, 'ro.board.platform')}\n")
        f.write(f"Android version: {get_prop(build_file, 'ro.system.build.version.release')}\n")
        f.write(f"Android API: {vndk}\n")
        f.write(f"Build fingerprint: {get_prop(build_file, 'ro.system.build.fingerprint')}\n")
        f.write(f"Build type: {get_prop(build_file, 'ro.build.type')}\n")
        f.write(f"Build tags: {get_prop(build_file, 'ro.build.tags')}\n")
        f.write(f"Build ID: {get_prop(build_file, 'ro.build.id')}\n")
        f.write(f"Security patch: {get_prop(build_file, 'ro.build.version.security_patch')}\n")
        f.write(f"#Raw Image Size#\n")
        f.write("```\n")

def merge_my() -> int:
    systemdir = os.path.join(IMG_DIR, "system")
    configdir = os.path.join(IMG_DIR, "config")
    dynamic_fs_dir = os.path.join(IMG_DIR, "dynamic_fs")
    target_fs = os.path.join(configdir, "system_fs_config")
    target_contexts = os.path.join(configdir, "system_file_contexts")
    if not os.path.exists(dynamic_fs_dir):
        os.makedirs(dynamic_fs_dir)
    for partition in os.listdir(IMG_DIR):
        if not partition.startswith('my_'):
            if partition != 'mi_ext':
                continue
        if not os.path.exists(systemdir):
            print("system.img is not unpacked，please continue after unpacking it.")
            return 1
        if not os.path.exists(os.path.join(IMG_DIR, partition)):
            print(f"{partition}.img is not unpacked，please continue after unpacking it.")
            return 1
        print(f"- Merging {partition} Partition")
        if os.path.isdir(os.path.join(IMG_DIR, partition)):
            rm_rf(os.path.join(systemdir, partition))
            rm_rf(os.path.join(IMG_DIR, partition, "lost+found"))
            move(os.path.join(IMG_DIR, partition), systemdir)
        if os.path.isfile(os.path.join(configdir, f"{partition}_file_contexts")):
            move(os.path.join(configdir, f"{partition}_file_contexts"), dynamic_fs_dir)
        fs_file = os.path.join(configdir, f"{partition}_fs_config")
        if os.path.exists(fs_file):
            move(fs_file, dynamic_fs_dir)
            rm_rf(os.path.join(configdir, f"{partition}_info"))
        if os.path.exists(os.path.join(dynamic_fs_dir, f"{partition}_file_contexts")):
            with open(os.path.join(dynamic_fs_dir, f"{partition}_file_contexts"), 'r+', encoding='utf-8') as f:
                lines = [i for i in f.readlines() if not i.startswith('/ u:')]
                lines = lines[1:]
                lines = [f"/system{i}" for i in lines if not "?" in i]
                lines.append(f"/system/{partition} u:object_r:system_file:s0\n")
            with open(target_contexts, 'r+', encoding='utf-8') as f:
                lines2 = f.readlines()
                f.seek(0)
                f.truncate()
                f.writelines([i for i in lines2 if not f"system/{partition} " in i])
                f.writelines(lines)
        if os.path.exists(os.path.join(dynamic_fs_dir, f"{partition}_fs_config")):
            with open(os.path.join(dynamic_fs_dir, f"{partition}_fs_config"), 'r+', encoding='utf-8') as f:
                lines = [i for i in f.readlines() if not i.startswith('/ 0')]
                lines = lines[1:]
                lines = [f"system/{i}" for i in lines]
                lines = lines[1:]
                if not lines[len(lines) - 1].endswith("\n"):
                    lines.append("\n")
                lines.append(f"system/{partition} 0 0 0755\n")
            with open(target_fs, 'r+', encoding='utf-8') as f:
                lines2 = f.readlines()
                lines2 = [i for i in lines2 if not f"system/{partition} " in i]
                f.seek(0)
                f.truncate()
                f.writelines(lines2)
                f.writelines(lines)

        print(f"Merged {partition}")
        with open(f"{systemdir}/system/build.prop", "a", encoding='utf-8', newline='\n') as f:
            f.write("\n")
            f.write(f"import /{partition}/build.prop\n")
    rm_rf(dynamic_fs_dir)
    return 0


def merge_parts_inside(parts: list) -> int:
    systemdir = f"{IMG_DIR}/system/system"
    configdir = f"{IMG_DIR}/config"
    dynamic_fs_dir = f"{IMG_DIR}/dynamic_fs"
    target_fs = f"{configdir}/system_fs_config"
    target_contexts = f"{configdir}/system_file_contexts"
    rm_rf(dynamic_fs_dir)
    os.makedirs(dynamic_fs_dir, exist_ok=True)
    for partition in parts:
        if not os.path.exists(systemdir):
            print("system.img is not unpacked，please continue after unpacking it.")
            return 1
        if not os.path.exists(os.path.join(IMG_DIR, partition)):
            print(f"{partition}.img is not unpacked，please continue after unpacking it.")
            return 1
        print(f"- Merging {partition} partition.")
        if os.path.isdir(os.path.join(IMG_DIR, partition)):
            rm_rf(os.path.join(systemdir, partition))
            rm_rf(os.path.join(IMG_DIR, partition, "lost+found"))
            move(os.path.join(IMG_DIR, partition), systemdir)
            rm_rf(os.path.join(IMG_DIR, 'system', partition))
            symlink(f"/system/{partition}", os.path.join(IMG_DIR, 'system', partition))

        if os.path.isfile(os.path.join(configdir, f"{partition}_file_contexts")):
            copy(os.path.join(configdir, f"{partition}_file_contexts"), dynamic_fs_dir)
        fs_file = os.path.join(configdir, f"{partition}_fs_config")
        if os.path.exists(fs_file):
            copy(fs_file, dynamic_fs_dir)
        if not os.path.isdir(f"{systemdir}/etc/init/config"):
            os.makedirs(f"{systemdir}/etc/init/config", exist_ok=True)
        skip_mount_file = f"{systemdir}/etc/init/config/skip_mount.cfg"
        if not os.path.exists(skip_mount_file):
            with open(skip_mount_file, 'w', encoding='utf-8'):
                ...
        with open(skip_mount_file, 'a+', encoding='utf-8') as f:
            f.write(f"/{partition}\n")
            f.write(f"/{partition}/*\n")
        if os.path.exists(os.path.join(dynamic_fs_dir, f"{partition}_file_contexts")):
            with open(os.path.join(dynamic_fs_dir, f"{partition}_file_contexts"), 'r+', encoding='utf-8') as f:
                lines = [i for i in f.readlines() if not i.startswith('/ u:')]
                lines = [f"/system/system{i}" for i in lines if not "?" in i]
                lines.append(f"/system/{partition} u:object_r:system_file:s0\n")
            with open(target_contexts, 'r+', encoding='utf-8') as f:
                lines2 = f.readlines()
                f.seek(0)
                f.truncate()
                f.writelines([i for i in lines2 if not f"system/{partition} " in i])
                f.writelines(lines)
        if os.path.exists(os.path.join(dynamic_fs_dir, f"{partition}_fs_config")):
            with open(os.path.join(dynamic_fs_dir, f"{partition}_fs_config"), 'r+', encoding='utf-8') as f:
                lines = [i for i in f.readlines() if not i.startswith('/ 0')]
                lines = [f"system/system/{i}" for i in lines]
                lines.append(f"system/{partition} 0 0 0644 /system/{partition}\n")
            with open(target_fs, 'r+', encoding='utf-8') as f:
                lines2 = f.readlines()
                lines2 = [i for i in lines2 if not f"system/{partition} " in i]
                f.seek(0)
                f.truncate()
                f.writelines(lines2)
                f.writelines(lines)
        print(f"Merged {partition}.")
    rm_rf(dynamic_fs_dir)
    return 0


def get_dir_size(path) -> int:
    size = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                file_path = os.path.join(root, name)
                if not os.path.isfile(file_path):
                    size += len(name)
                size += os.path.getsize(file_path)
            except (PermissionError, BaseException, Exception):
                size += 1
    return size


def repack_image() -> int:
    systemdir = f"{IMG_DIR}/system"
    fs = f"{IMG_DIR}/config/system_fs_config"
    con = f"{IMG_DIR}/config/system_file_contexts"
    with open(fs, 'a+', encoding='utf-8') as f:
        for i in ['system/system/bin/bootctl 0 2000 0755',
                  'system/system/bin/busybox_phh 0 2000 0755',
                  'system/system/bin/getSPL 0 2000 0755',
                  'system/system/bin/gsid 0 2000 0755',
                  'system/system/bin/objdump 0 2000 0755',
                  'system/system/bin/phh-on-boot.sh 0 2000 0755',
                  'system/system/bin/rw-system.sh 0 2000 0755',
                  'system/system/bin/vintf 0 2000 0755',
                  'system/system/bin/vndk-detect 0 2000 0755',
                  'system/system/bin/wificonf 0 2000 0755',
                  'system/system/etc/init/config 0 0 0755',
                  'system/system/etc/init/config/skip_mount.cfg 0 0 0644',
                  'system/system/system_ext/etc/init 0 0 0755',
                  'system/system/system_ext/etc/init/config 0 0 0755',
                  'system/system/system_ext/etc/init/config/skip_mount.cfg 0 0 0644',
                  'system/system/etc/init/gsid.rc 0 0 0644',
                  'system/system/etc/init/vndk.rc 0 0 0644',
                  'system/system/etc/init/wificonf.rc 0 0 0644',
                  'system/system/etc/usb_audio_policy_configuration.xml 0 0 0644']:
            f.write(i + '\n')
    with open(con, 'a+', encoding='utf-8') as f:
        for i in [
            '/system/system/bin/bootctl u:object_r:system_file:s0',
            '/system/system/bin/busybox_phh u:object_r:system_file:s0',
            '/system/system/bin/getSPL u:object_r:system_file:s0',
            '/system/system/bin/gsid u:object_r:gsid_exec:s0',
            '/system/system/bin/vintf u:object_r:system_file:s0',
            '/system/system/bin/vndk-detect u:object_r:update_engine_exec:s0',
            '/system/system/bin/wificonf u:object_r:wificond_exec:s0',
            '/system/system/etc/init/config u:object_r:system_file:s0',
            r'/system/system/etc/init/config/skip_mount\.cfg u:object_r:system_file:s0',
            '/system/system/system_ext/etc/init u:object_r:system_file:s0',
            '/system/system/system_ext/etc/init/config u:object_r:system_file:s0',
            r'/system/system/system_ext/etc/init/config/skip_mount\.cfg u:object_r:system_file:s0',
            r'/system/system/etc/init/vndk\.rc u:object_r:system_file:s0',
            r'/system/system/etc/init/wificonf\.rc u:object_r:system_file:s0',
            r'/system/system/etc/usb_audio_policy_configuration\.xml u:object_r:vendor_configs_file:s0',
            r'/system/system/bin/phh-on-boot\.sh u:object_r:update_engine_exec:s0',
            r'/system/system/bin/rw-system\.sh u:object_r:update_engine_exec:s0',
        ]:
            f.write(i + '\n')
    fspatch(systemdir, fs)
    contextpatch(systemdir, con)
    os.makedirs(f"{IMG_DIR}/out", exist_ok=True)
    choice = input("Choose a FileSystem to Repack:[ext(default)/erofs]")
    if choice == "erofs":
        return call(["mkfs.erofs", "-zlz4hc,9", "--mount-point", f"/system", "--fs-config-file",
                     f"{IMG_DIR}/config/system_fs_config",
                     "--file-contexts", f"{IMG_DIR}/config/system_file_contexts", f"{IMG_DIR}/out/system.img",
                     f"{IMG_DIR}/system"], out_=False)
    else:
        size = get_dir_size(systemdir)
        size2 = int(size / 4096 + 4096 * 10)
        if call(['mke2fs', '-O', '^has_journal', '-t', 'ext4', '-b', '4096', '-L', 'system', '-I', '256', '-M',
                 '/system', f'{IMG_DIR}/out/system.img', f'{size2}']):
            return 1
        if call(
                ['e2fsdroid', '-e', '-T', '1230768000', '-C', f'{IMG_DIR}/config/system_fs_config', '-S',
                 f'{IMG_DIR}/config/system_file_contexts', '-f', f'{IMG_DIR}/system', '-a', f'/system',
                 f'{IMG_DIR}/out/system.img']
        ):
            return 1
        if which("resize2fs"):
            if call(["resize2fs", "-M", f'{IMG_DIR}/out/system.img'], extra_path=False):
                return 1
    return 0


def clean_up(clean_img_dir=False) -> int:
    print("Cleaning up...")
    rm_rf(EXTRACT_DIR)
    if clean_img_dir:
        rm_rf(IMG_DIR)
    rm_rf(os.path.join(IMG_DIR, "system"))
    rm_rf(os.path.join(IMG_DIR, "config"))
    print("Done.")
    return 0


def main() -> int:
    if check_tools():
        return 1
    clean_up(True)
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)
    if not os.path.exists(EXTRACT_DIR):
        os.makedirs(EXTRACT_DIR)
    dest_path = None
    print("========================================")
    print("    OEM Generic System Image Maker")
    print("========================================")
    print(f"  Version:{__version__}")
    print(f"  Provided by {'|'.join(__author__)}")
    print("========================================")
    print()
    print("Please Select Operation：")
    print("1. Download and process")
    print("2. Process local roms")
    print("3. Exit")
    mode = input("Select (1/2/3):")
    if mode == "3":
        return 0
    elif mode == '1':
        url = input("Enter download url([q] to exit):")
        if url:
            filename = url.split("/")[-1].split('?')[0]
            dest_path = os.path.join(prog_path, filename)
            download([url], prog_path)
    else:
        dest_path = select_file()
    if not dest_path:
        print(f"[{dest_path}] not found.")
        return 1
    if extract_rom(dest_path):
        return 1
    if extract_images():
        return 1
    if decompose_images():
        return 1
    if modify_parts():
        return 1
    if generate_markdown(f"{IMG_DIR}/out/info.md"):
        return 1
    if merge_my():
        return 1
    if merge_parts_inside(["system_ext", "product"]):
        return 1
    if repack_image():
        return 1
    if clean_up():
        return 1
    print(f"Done!The GSi File is {IMG_DIR}/out/system.img.")
    replace(f"{IMG_DIR}/out/info.md", "#Raw Image Size#\n", f"Raw Image Size: {round(os.path.getsize(f'{IMG_DIR}/out/system.img')/1024**3, 2)} GB\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
