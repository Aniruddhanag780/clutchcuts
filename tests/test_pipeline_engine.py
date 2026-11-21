import subprocess
import unittest
from unittest.mock import patch

import yt_dlp

import pipeline_engine


class StubYoutubeDL:
    def __init__(self, result):
        self.result = result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def extract_info(self, url, download):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class ExtractVideoInfoTests(unittest.TestCase):
    def test_uses_default_player_first_then_retries_alternate_strategies(self):
        info = {"title": "test video", "duration": 120}
        attempts = [
            StubYoutubeDL(yt_dlp.utils.DownloadError("no player response")),
            StubYoutubeDL(yt_dlp.utils.DownloadError("no player response")),
            StubYoutubeDL(info),
        ]
        logs = []

        with (
            patch.object(pipeline_engine, "get_config", return_value={"deno_path": None}),
            patch.object(yt_dlp, "YoutubeDL", side_effect=attempts) as youtube_dl,
        ):
            result = pipeline_engine.extract_video_info("https://youtu.be/example", logs.append)

        self.assertEqual(result, info)
        self.assertEqual(youtube_dl.call_count, 3)
        self.assertFalse(youtube_dl.call_args_list[0].args[0]["getcomments"])
        self.assertNotIn("extractor_args", youtube_dl.call_args_list[0].args[0])
        self.assertTrue(youtube_dl.call_args_list[1].args[0]["getcomments"])
        self.assertFalse(youtube_dl.call_args_list[2].args[0]["getcomments"])
        self.assertEqual(len(logs), 2)

    def test_uses_opt_in_browser_cookies_for_video_details(self):
        info = {"title": "test video", "duration": 120}
        with (
            patch.object(
                pipeline_engine,
                "get_config",
                return_value={"deno_path": None, "cookies_browser": "chrome"},
            ),
            patch.object(yt_dlp, "YoutubeDL", return_value=StubYoutubeDL(info)) as youtube_dl,
        ):
            result = pipeline_engine.extract_video_info("https://youtu.be/example", lambda _: None)

        self.assertEqual(result, info)
        self.assertEqual(youtube_dl.call_args.args[0]["cookiesfrombrowser"], ("chrome",))

    def test_explains_youtube_bot_verification_error(self):
        blocked = yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")
        attempts = [StubYoutubeDL(blocked) for _ in range(3)]
        with (
            patch.object(pipeline_engine, "get_config", return_value={"deno_path": None}),
            patch.object(yt_dlp, "YoutubeDL", side_effect=attempts),
        ):
            with self.assertRaisesRegex(RuntimeError, "cannot access cookies from your PC"):
                pipeline_engine.extract_video_info("https://youtu.be/example", lambda _: None)

    def test_retries_slice_download_with_default_player_selection(self):
        command = [
            "python", "-m", "yt_dlp", "--extractor-args",
            "youtube:player_client=android,ios,tv,web", "https://youtu.be/example",
        ]
        failed = subprocess.CalledProcessError(1, command, stderr="no player response")
        succeeded = subprocess.CompletedProcess(command, 0)
        logs = []

        with patch("pipeline_engine.subprocess.run", side_effect=[failed, succeeded]) as run:
            pipeline_engine.download_video_slice(command, 1, logs.append)

        self.assertEqual(run.call_count, 2)
        self.assertIn("--extractor-args", run.call_args_list[0].args[0])
        self.assertNotIn("--extractor-args", run.call_args_list[1].args[0])
        self.assertTrue(any("default player selection" in message for message in logs))

    def test_browser_cookie_settings_cover_api_and_cli(self):
        cfg = {"cookies_browser": "chrome"}
        self.assertEqual(pipeline_engine.get_cookie_options(cfg), {"cookiesfrombrowser": ("chrome",)})
        self.assertEqual(pipeline_engine.get_cookie_cli_args(cfg), ["--cookies-from-browser", "chrome"])


if __name__ == "__main__":
    unittest.main()
