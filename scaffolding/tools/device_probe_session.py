#!/usr/bin/env python3
"""One ACL session per measurement window; query only available dynamic sensors."""
import argparse
import ctypes
import json
import socket
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--device', type=int, required=True)
    p.add_argument('--card', type=int, required=True)
    p.add_argument('--chip', type=int, required=True)
    p.add_argument('--session', action='store_true')
    a = p.parse_args()
    acl = ctypes.CDLL('libascendcl.so')
    def check(code, operation):
        if code:
            raise RuntimeError(f'{operation}: {code}')
    check(acl.aclInit(None), 'aclInit')
    try:
        check(acl.aclrtSetDevice(a.device), 'aclrtSetDevice')
        try:
            acl.aclrtGetSocName.restype = ctypes.c_char_p
            physical = ctypes.c_uint()
            check(acl.aclrtGetPhyDevIdByLogicDevId(a.device, ctypes.byref(physical)), 'physical mapping')
            identity = {'device': a.device, 'physical_device': socket.gethostname()+'/physical-'+str(physical.value),
                        'soc_version': acl.aclrtGetSocName().decode(), 'card': a.card, 'chip': a.chip}
            dcmi = ctypes.CDLL('/usr/local/Ascend/driver/lib64/driver/libdcmi.so')
            initialized = dcmi.dcmi_init()
            for _ in sys.stdin if a.session else [None]:
                observation = {'observed_monotonic': time.monotonic(), 'frequencies': [],
                    'vector_frequency': 'unknown', 'vector_frequency_stability_verified': False,
                    'dcmi_init_returncode': initialized}
                if initialized == 0:
                    for kind, label in ((7, 'aicore_current'), (9, 'aicore_max'), (12, 'vectorcore_current')):
                        frequency = ctypes.c_uint()
                        code = dcmi.dcmi_get_device_frequency(a.card, a.chip, kind, ctypes.byref(frequency))
                        observation['frequencies'].append({'kind':kind, 'label':label, 'returncode':code,
                            'value': frequency.value if code == 0 else None, 'unit':'MHz'})
                        if kind == 12 and code == 0:
                            observation['vector_frequency'] = frequency.value
                print(json.dumps({'identity':identity, 'observation':observation}) if a.session else json.dumps(identity), flush=True)
                if not a.session:
                    print(json.dumps(observation), file=sys.stderr, flush=True)
        finally:
            check(acl.aclrtResetDevice(a.device), 'aclrtResetDevice')
    finally:
        check(acl.aclFinalize(), 'aclFinalize')


if __name__ == '__main__':
    main()
