#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盲盒统计GUI启动脚本 - 抑制PNG警告
"""

import sys
import os
import warnings

# 抑制所有警告
warnings.filterwarnings("ignore")

# 重定向stderr来抑制libpng警告（可选）
# 取消下面两行的注释来完全隐藏这些警告
# import io
# sys.stderr = io.StringIO()

from blind_box_gui import main

if __name__ == "__main__":
    main()
