# 🎸 随机喜多 - AstrBot Plugin

在聊天中随机发送喜多郁代（来自《孤独摇滚！》结束乐队）的图片~

## 功能

| 命令 | 说明 |
|------|------|
| `/随机喜多` | 随机发送一张喜多图片 |
| `/上传喜多` | 发送图片或回复带图消息来添加图片到图库 |
| `/喜多数量` | 查看当前图库中的图片数量 |

## 安装

1. 在 AstrBot WebUI 插件市场中搜索「随机喜多」并安装
2. 或手动克隆到 `data/plugins/` 目录：
   ```bash
   git clone https://github.com/OHINOH114514/astrbot_plugin_random_kita.git
   ```

## 预设图片

插件自带 426 张预设喜多图，安装后在 WebUI 插件 Pages → settings 中点击「下载预设图片」即可获取。

如需自定义图片地址，请在 WebUI 插件配置中修改 `github_release_url`。

## 手动上传

你也可以通过 `/上传喜多` 命令在聊天中上传图片，或直接往 `data/plugin_data/astrbot_plugin_random_kita/images/` 目录丢图。

## 许可证

MIT
