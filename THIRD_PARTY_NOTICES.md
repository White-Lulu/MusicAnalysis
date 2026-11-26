# 第三方来源与授权

根目录的 MIT License 适用于本项目自有代码和文档，不替代下列组件的许可。本仓库不分发第三方模型权重、FFmpeg 二进制、用户音频或 Python 运行环境；安装脚本按 [assets.py](music_analysis/assets.py) 的来源和校验值下载模型。

## 音乐模型

| 组件 | 本项目使用范围 | 上游授权说明 |
| --- | --- | --- |
| [MAEST](https://github.com/palonso/MAEST) / [Discogs-MAEST 519 转换权重](https://huggingface.co/mtg-upf/discogs-maest-30s-pw-129e-519l) | `mtg-upf/discogs-maest-30s-pw-129e-519l`，含配套特征提取文件 | MTG 的[模型政策](https://essentia.upf.edu/models.html)为 CC BY-NC-SA 4.0；该 Hugging Face 转换页的许可字段未完整填写。原研究代码与权重的许可范围应分别核对，不将转换权重或附带代码重新许可为 MIT。 |
| [LAION CLAP HTSAT Unfused](https://huggingface.co/laion/clap-htsat-unfused) | 音频／文本特征与匹配 | 该模型页标注 Apache-2.0；[CLAP 研究代码](https://github.com/LAION-AI/CLAP)的许可单独适用。 |
| [MTG / Essentia 模型](https://essentia.upf.edu/models.html) | Discogs-EffNet、MTG-Jamendo instrument / moodtheme、MSD-MusiCNN、DEAM 的冻结 TensorFlow 图 | CC BY-NC-SA 4.0；可向 MTG 申请其他授权，见[官方许可说明](https://essentia.upf.edu/licensing_information.html)。本项目不安装 Essentia C++ / Python 库，模型图通过 TensorFlow 执行。 |
| [Beat This!](https://github.com/CPJKU/beat_this#license) | `beat-this` 推理包与 `final0.ckpt` | 上游明确将代码和已发布模型权重置于 MIT 许可下。作者：Francesco Foscarin、Jan Schlüter、Gerhard Widmer。 |
| [NemoraSonar 1.1](https://github.com/Nikenmar/NemoraSonar#license) | ONNX 模型、元数据与标签 | MIT，Copyright (c) 2026 NIKENMAR。包含 EfficientAT `mn10_as`，MIT，Copyright (c) 2022 Florian Schmid。下载时保留发布包中的 `LICENSE` 和 `THIRD_PARTY_LICENSES.md`。 |

模型页面与许可证原文是授权依据。权重、附带代码、训练音频与数据库的权利范围可能不同；本项目没有取得用户音乐或第三方训练音频的再分发许可。

## 音频处理、运行依赖与参考实现

- [FFmpeg](https://ffmpeg.org/legal.html)：由 `imageio-ffmpeg` 提供命令行程序。FFmpeg 的 LGPL / GPL 条件取决于具体构建，不能按本项目 MIT 许可重新分发。可通过实际二进制的 `-L` 和 `-buildconf` 查看构建信息。
- [librosa](https://github.com/librosa/librosa)：ISC License；用于音频特征与信号分析。
- PyTorch / torchaudio、TensorFlow、Transformers、ONNX Runtime、FastAPI、NumPy、SoundFile、Mutagen、PyCryptodome 等通过依赖清单安装。各自发行包的许可证继续适用，源码仓库不内嵌这些包。
- [taurusxin/ncmdump](https://github.com/taurusxin/ncmdump)：NCM 文件布局和解包流程参考，MIT License；本项目提供 Python 导入实现，不附带其构建工程。
- [poppinlp/netease-music-cache-decoder](https://github.com/poppinlp/netease-music-cache-decoder)：UC 缓存还原方式的参考。本项目使用格式层面的逐字节还原，不附带该项目代码。该参考不授予任何歌曲内容的使用权。

## 字体与视觉素材

- **Inter**：Copyright (c) The Inter Project Authors，SIL Open Font License 1.1。字体文件随本仓库提供，完整许可见 [Inter-LICENSE.txt](music_analysis/web/Inter-LICENSE.txt)。
- **装饰封套**：本项目通过 AI 图像生成得到的六款装饰图，随应用用于界面展示。它们不对应真实歌曲或唱片的专辑封面。
- **README 截图**：来自本应用界面，曲名、艺人、批次名称已匿名化；不包含或分发音乐音频。
