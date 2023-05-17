#!/bin/env python3
"""
Match layers to layerWidgets    
"""
import re
layerComboBox = ['fuels','elevation','cbd','cbf']
layer_names = ['Fuels','mdt.asc']
for lcb in layerComboBox:
    if lcb == 'fuels':
        regex = re.compile('model.*asc|[Ff]uel')
    elif lcb == 'elevation':
        regex = re.compile('mdt.*asc|[Ee]levation')
    else:
        continue
    for n in layer_names:
        if a:=re.match(regex,n):
            print(lcb,'set to ',a.string)
            break
    else:
        print('set to none')
