"""Test-only unchanged reviewed offline IO barrier (AA/search qualification v4).

Copied as inert fixture source so installed tests do not depend on /tmp packages.
This is not a product reader, a sandbox, or an archive authority.
"""
import builtins
import io
import os
from pathlib import Path
import sys

def install_read_barrier(deny_root):
    """Deny original-tree reads by trusted offline helpers in this subprocess.

    CPython's ``open`` audit event omits dir_fd. Normalize os.open's argument
    using the actual directory descriptor BEFORE that event; never infer its
    base from cwd. Ambiguous relative opens bypassing these wrappers fail closed.
    Ordinary builtins/io.open relative paths are explicitly normalized as well.
    This is an IO provenance guard for fixed reviewed Python helpers, not a
    sandbox against arbitrary native code or malicious in-process Python.
    """
    root=Path(deny_root).resolve()
    old_os_open,old_builtin_open,old_io_open=os.open,builtins.open,io.open
    old_close,old_readlink=os.close,os.readlink

    def fail():raise RuntimeError('original repository read denied or ambiguous offline path')
    def check_path(value):
        path=Path(os.fsdecode(os.fspath(value)))
        if not path.is_absolute():fail()
        lexical=Path(os.path.abspath(path));resolved=path.resolve()
        if lexical==root or lexical.is_relative_to(root) or resolved==root or resolved.is_relative_to(root):fail()
        return path
    def fd_path(fd):
        if type(fd) is not int or fd<0:fail()
        try:target=old_readlink('/proc/self/fd/'+str(fd))
        except OSError:fail()
        # Deleted/anonymous descriptors have no unambiguous stable pathname.
        if not target.startswith('/') or target.endswith(' (deleted)'):fail()
        return check_path(target)
    def normalized(value,dir_fd=None):
        path=Path(os.fsdecode(os.fspath(value)))
        if not path.is_absolute():
            base=Path.cwd() if dir_fd is None else fd_path(dir_fd)
            path=base/path
        return check_path(path)
    def checked_os_open(path,flags,mode=0o777,*,dir_fd=None):
        actual=normalized(path,dir_fd)
        # Passing an absolute path deliberately removes audit's dir_fd ambiguity.
        # The kernel's returned descriptor is checked again before exposing it.
        fd=old_os_open(actual,flags,mode)
        try:fd_path(fd)
        except BaseException:old_close(fd);raise
        return fd
    def checked_file_open(original,file,*args,**kwargs):
        actual=fd_path(file) if type(file) is int else normalized(file)
        stream=original(file if type(file) is int else actual,*args,**kwargs)
        try:fd_path(stream.fileno())
        except BaseException:stream.close();raise
        return stream
    def checked_builtin_open(file,*args,**kwargs):return checked_file_open(old_builtin_open,file,*args,**kwargs)
    def checked_io_open(file,*args,**kwargs):return checked_file_open(old_io_open,file,*args,**kwargs)
    def denied(event,args):
        if event not in ('open','os.listdir','os.scandir') or not args:return
        value=args[0]
        if type(value) is int:fd_path(value);return
        if event=='open':
            # Absolute only. A saved os.open callable could supply a hidden
            # dir_fd; an audit event alone cannot safely interpret that string.
            check_path(value)
        else:
            normalized('.' if value is None else value)
    os.open=checked_os_open;builtins.open=checked_builtin_open;io.open=checked_io_open
    sys.addaudithook(denied)
