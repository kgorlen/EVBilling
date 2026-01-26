'''
Created on Jun 10, 2024

@author: Keith gorlen@comcast.net

References:
    https://pypi.org/project/pyemvue/
    https://github.com/magico13/PyEmVue
    https://github.com/magico13/PyEmVue/blob/master/api_docs.md

'''
import pyemvue
from pyemvue.enums import Scale, Unit
import sys
import keyring
import tempfile

SYSTEM = 'emporiavue'
USERNAME = 'pws.ev.energy@gmail.com'

def print_recursive(usage_dict, info, depth=0):
    for gid, device in usage_dict.items():
        for channelnum, channel in device.channels.items():
            name = channel.name
            if name == 'Main':
                name = info[gid].device_name
            print('-'*depth, f'{gid} {channelnum} {name} {channel.usage} kwh')
            if channel.nested_devices:
                print('Nested device:', channel.nested_devices)
                print_recursive(channel.nested_devices, info, depth+1)

if __name__ == '__main__':
    
    vue = pyemvue.PyEmVue()

    password = keyring.get_password(SYSTEM, USERNAME)
    if password is None:
        print(f'keyring.get_password("{SYSTEM}", "{USERNAME}") Failed')
        print('Set Emporia Vue password with the command:')
        print(f'\tkeyring set {SYSTEM} {USERNAME}')
        print(f'{SYSTEM} {USERNAME} password not found', file=sys.stderr)
    
    fp = tempfile.TemporaryFile(delete=True, delete_on_close=False)
    with fp:
        vue.login(username=USERNAME, password=password, token_storage_file=fp.name)
        
        devices = vue.get_devices()
        
        device_gids = []
        device_info = {}
        for device in devices:
            if not device.device_gid in device_gids:
                device_gids.append(device.device_gid)
                device_info[device.device_gid] = device
            else:
                device_info[device.device_gid].channels += device.channels
        
        device_usage_dict = vue.get_device_list_usage(deviceGids=device_gids, instant=None, scale=Scale.MINUTE.value, unit=Unit.KWH.value)
        print('device_gid channel_num name usage unit')
        print_recursive(device_usage_dict, device_info)