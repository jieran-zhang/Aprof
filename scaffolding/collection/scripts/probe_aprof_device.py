#!/usr/bin/env python3
"""Read runtime device attributes with an explicit logical device."""
import ctypes
import json
import os
import socket

lib = ctypes.CDLL('libascendcl.so')
lib.aclrtGetSocName.restype = ctypes.c_char_p

def checked(code, operation):
    if code:
        raise RuntimeError(f'{operation}: {code}')

checked(lib.aclInit(None), 'aclInit')
checked(lib.aclrtSetDevice(0), 'aclrtSetDevice')
result = {'host': socket.gethostname(), 'visible_physical_devices': os.getenv('ASCEND_RT_VISIBLE_DEVICES'),
          'logical_device': 0, 'soc': lib.aclrtGetSocName().decode(), 'attributes': {}}
for name, attribute in [('ai_core_count', 101), ('cube_core_count', 102), ('vector_core_count', 201), ('ub_bytes_per_vector_core', 204)]:
    value = ctypes.c_int64()
    code = lib.aclrtGetDeviceInfo(0, attribute, ctypes.byref(value))
    result['attributes'][name] = {'value': value.value if code == 0 else None, 'status_code': code,
                                 'source': 'aclrtGetDeviceInfo', 'attribute_id': attribute}
checked(lib.aclrtResetDevice(0), 'aclrtResetDevice')
checked(lib.aclFinalize(), 'aclFinalize')
print(json.dumps(result, sort_keys=True))
