---
title: "Free tool stack: posting, clipping, video and image gen"
created: 2026-11-09
source: https://claude.ai/artifact/8ZK1Pii6H3xar7aebmUzhZ
tags: [claude-docs, tools, posting, clipping, ai-video, ai-image, reference]
aliases: [Free tool stack]
related: ["[[Bot Teams Review and Rebuild Plan]]", "[[Matt Chibbs 5M Reach Plan]]", "[[2026-11-09 Claude Docs Digest]]"]
---

# Free tool stack: posting, clipping, video and image gen

## The picks

Posting and clipping can be truly free. Quality video gen can't on the current laptops; the cheapest real option is about **$0.30 per 5-second clip**.

| Job | Pick | Runner-up | Where free has limits |
| --- | --- | --- | --- |
| Posting | Buffer free | Postiz, self-hosted | 3 channels, 10 queued posts each |
| Clipping | autoclip (open source) | OpenShorts | Free local AI picks weaker moments; a paid key fixes that for cents |
| Captions | whisper.cpp | faster-whisper on the MSI | Truly free, no catch |
| Images | FLUX schnell or Qwen-Image | RunPod at under 2¢ an image | Slow on the laptops |
| Video | Wan 2.2 on RunPod, $0.30 a clip | LTX-2 for clips with sound | Not free; free local route exists but very slow |
| Research | vidIQ free | Skip Windsor | YouTube only, 150 AI credits a month |

Windsor.ai doesn't post videos (Instagram images only) — not worth connecting for posting.

## Windsor.ai and vidIQ: free, but neither posts your videos

Windsor mostly reads stats; vidIQ is YouTube research.

| Tool | Free tier | Cheapest paid | Posts for you? |
| --- | --- | --- | --- |
| [Windsor.ai](https://windsor.ai/pricing/) | 30-day trial (10 sources, 15 accounts), then Forever Free: 1 source, 1 account | Basic, $19/mo yearly or $23/mo monthly | Instagram image posts only. FB, TikTok, YouTube are read-only stats ([guide](https://windsor.ai/how-to-use-windsor-ai-for-social-media/)) |
| [vidIQ](https://1of10.com/blog/vidiq-pricing/) | 150 AI credits/mo, extension stats, limited daily ideas, small keyword tool | Boost, $199/yr or $39/mo | No. Research, titles, thumbnails, analytics. YouTube-focused |

Windsor's free plan after trial covers one account, so it can't watch IG, TikTok and YouTube together. vidIQ prices are from a competitor's July 2026 summary — check before paying.

## Posting: Buffer's free plan beats self-hosting for now

Buffer free (already in use) is the easiest real free option: 3 channels, 10 queued posts each, and a free API key. Self-hosted Postiz is free software, but TikTok and Meta require your own developer apps approved first.

| Option | Cost | Limits | Catch |
| --- | --- | --- | --- |
| [Buffer](https://buffer.com/pricing) free | $0 | 3 channels, 10 scheduled posts per channel, 1 API key (1,000 requests/channel/month) | A 4th channel (e.g. Facebook) = $5/mo per channel on Essentials |
| [Postiz](https://github.com/gitroomhq/postiz-app) self-hosted | $0 software (AGPL-3.0) + a server | Unlimited posts, ~34 platforms incl. Kick and Twitch | Run Docker, Postgres, Redis; register your own app per platform ([provider setup](https://docs.postiz.com/self-host/providers/overview.md)) |
| [Postiz cloud](https://postiz.com/pricing) | $29/mo for 5 channels | Unlimited posts, 60 min AI clipping/month | No free tier, 7-day trial only |

Platform requirements when posting through your own app (Postiz or a script):
- **TikTok:** an app with the Content Posting API. Until TikTok audits it, every post is private ([docs](https://developers.tiktok.com/doc/content-posting-api-get-started)).
- **Instagram and Facebook:** a Meta developer app. Meta and YouTube approval usually takes over a month ([Postiz FAQ](https://postiz.com/pricing)).
- **YouTube:** a Google Cloud project with the Data API; default quota 10,000 units/day ([docs](https://developers.google.com/youtube/v3/getting-started)).

Buffer has already done those approvals — that's why it's the pick. Postiz only makes sense past 3 channels.

## Clipping and captions: autoclip for the full job, whisper.cpp for captions

Free open-source clippers do the OpusClip job (pick highlights, reframe 9:16, burn captions). Weak spot: choosing the best moments, which needs a strong AI model.

| Repo | What it does | Free? | Runs on | Catch |
| --- | --- | --- | --- | --- |
| [autoclip](https://github.com/artbyjazi/autoclip) (MIT, 214★) | Highlights, speaker-tracked 9:16 reframe, 4 caption styles | Yes, fully offline with Ollama | Mac, Windows, Linux | Pre-1.0; small local model picks "mediocre" clips per its README |
| [OpenShorts](https://github.com/mutonby/openshorts) (MIT core, 7.1k★) | Highlights, face tracking, captions, dubbing, API | Needs a Gemini key for AI steps | Docker; Windows via WSL2 | Most complete, but not fully free or local |
| [AI YouTube Shorts Generator](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator) (MIT, 5.6k★) | YouTube link → ranked shorts, face crop | Needs OpenAI, Gemini or MuAPI key | Python + ffmpeg | Ranking always uses a paid API |
| [OpenClipper](https://github.com/GrepCut/OpenClipper) (MIT) | Desktop app, 20+ caption presets, reframe | Yes, local transcription | Windows first | 4★, very new; posting not verified |
| [ClippedAI](https://github.com/Shaarav4795/ClippedAI) | Clips + animated subtitles | Yes | Mac, Windows | Non-commercial license |

For captions alone (add to the `make_captions` script):
- **[whisper.cpp](https://github.com/ggml-org/whisper.cpp):** free, runs on the Mac GPU via Metal on Apple Silicon. Large model ≈ 3.9 GB memory.
- **[faster-whisper](https://github.com/SYSTRAN/faster-whisper):** ~4× faster than original Whisper; best on the MSI's NVIDIA card.
- **[WhisperX](https://github.com/m-bain/whisperX):** word-level timing for pop-on captions; large-v2 fits under 8 GB GPU memory.

For Cooked On Stream: autoclip with a paid AI key for clip-picking beats a free local model. Only the transcript is sent, so a few cents per video (estimate).

## Video and image gen: free models, not free to run well

Open models are free to download, but quality video needs a big GPU. Realistic move: rent one per clip, ~$0.30–$0.50 per 5-second video.

### The open models

| Model | Type | License | GPU memory |
| --- | --- | --- | --- |
| [Wan 2.2](https://github.com/Wan-Video/Wan2.2) | Video, 720p, text/image → video | Apache-2.0, commercial OK | 5B: 24 GB (official example); 14B: 80 GB |
| [HunyuanVideo 1.5](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5) | Video, 480p/720p, upscale to 1080p | Not confirmed | 14 GB with offloading; ~75 s/clip on RTX 4090 |
| [LTX-2](https://github.com/Lightricks/LTX-2) | Video with matching audio, up to 4K | Not confirmed | Not stated; 66 GB download |
| [FLUX.1 schnell](https://github.com/black-forest-labs/flux) | Image | Apache-2.0, commercial OK | Not stated |
| [FLUX.1 dev](https://github.com/black-forest-labs/flux) | Image, higher quality | Non-commercial without paid license | Not stated |
| [Qwen-Image](https://github.com/QwenLM/Qwen-Image) | Image + editing, good with text | Apache-2.0, commercial OK | No official figure |

Runners: [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (Apple Silicon OK, claims 4 GB min) and [WanGP](https://github.com/deepbeepmeep/Wan2GP) (claims some models on 4–6 GB). These open models are a step below the top closed models available through Higgsfield; LTX-2 is closest for clips with sound.

### What the gear can do
- **MSI GF65 (GTX 1660 Ti, 6 GB):** images with FLUX schnell or Qwen-Image via ComfyUI, slowly. Video only via WanGP low-memory mode — many minutes per short clip. Testing only.
- **MacBook:** depends on chip/RAM (unknown). Apple Silicon 16 GB+ can run image models in ComfyUI; video slow. Intel Mac can't do either well.
- **iPhone 17 Pro:** not for running these models.

### Cheapest way to run them

| Route | Cost | Notes |
| --- | --- | --- |
| [RunPod](https://www.runpod.io/pricing) pay-per-request | Wan 2.2 i2v 720p 5 s: $0.30. Wan 2.6 t2v 5 s: $0.50. FLUX schnell ≈ $0.003/image. Qwen-Image: $0.02 | No setup, pay per clip |
| RunPod rented RTX 4090 | $0.89/hour | ~2¢ per HunyuanVideo clip at 75 s each, plus setup time |
| [Google Colab](https://research.google.com/colaboratory/faq.html) free | $0 | Limits unpublished; free tier bans web apps like ComfyUI |
| Kaggle free GPU | $0 | Weekly hours unconfirmed |
| [Gemini API](https://ai.google.dev/gemini-api/docs/pricing) | No free tier for Veo or Nano Banana | Paid only via API |

Kling, Hailuo and Meta AI free credits are unconfirmed — worth checking manually; free daily credits there would beat everything above for quick tests.

## Sources
- [Windsor.ai pricing](https://windsor.ai/pricing/), [Windsor social guide](https://windsor.ai/how-to-use-windsor-ai-for-social-media/)
- [vidIQ pricing summary, 1of10](https://1of10.com/blog/vidiq-pricing/)
- [Buffer pricing](https://buffer.com/pricing)
- [Postiz repo](https://github.com/gitroomhq/postiz-app), [Postiz pricing](https://postiz.com/pricing), [Postiz provider setup](https://docs.postiz.com/self-host/providers/overview.md)
- [TikTok Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started)
- [YouTube Data API](https://developers.google.com/youtube/v3/getting-started)
- [RunPod pricing](https://www.runpod.io/pricing), [Google Colab FAQ](https://research.google.com/colaboratory/faq.html), [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Notebookcheck MSI GF65 9SD review](https://www.notebookcheck.net/MSI-GF65-9SD-Laptop-Review-GeForce-GTX-1660-Ti-for-under-1000.439783.0.html)
