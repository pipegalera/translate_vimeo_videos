from faster_whisper import WhisperModel
import os
import ffmpeg
import time
import sys
import threading

def spinner_animation(message, stop_event):
    frames = ["⢿", "⣻", "⣽", "⣾", "⣷", "⣯", "⣟", "⡿"]
    start_time = time.time()

    while not stop_event.is_set():
        for frame in frames:
            if stop_event.is_set():
                break
            elapsed_time = time.time() - start_time
            sys.stdout.write(f'\r{message} {frame} ({elapsed_time:.1f}s)')
            sys.stdout.flush()
            time.sleep(0.1)
    sys.stdout.write('\r')
    sys.stdout.flush()

def start_loading(message):
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=spinner_animation, args=(message, stop_event))
    spinner_thread.start()
    return stop_event, spinner_thread

def get_output_path(input_video):
    """
    Create output path in 'videos_translated' folder with same filename as input
    """
    # Create videos_translated directory if it doesn't exist
    output_dir = "videos_translated"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get the original filename without path
    input_filename = os.path.basename(input_video)

    # Create output path
    output_path = os.path.join(output_dir, input_filename)

    return output_path

def extract_audio(input_audio):
    """
    Extract audio from video file
    """
    try:
        # Extract audio using ffmpeg
        output_audio = "extracted_audio.wav"
        stream = ffmpeg.input(input_audio)
        stream = ffmpeg.output(stream, output_audio, acodec='pcm_s16le', ac=1, ar='16k')
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        return output_audio
    except ffmpeg.Error as e:
        print('An error occurred while extracting audio:', e.stderr.decode())
        return None

def transcribe_audio(audio_path, model="large-v3", source_lang= None):
    """
    Transcribe audio using Whisper model
    """
    try:
        # Initialize the Whisper model
        model = WhisperModel(model, device="cpu", compute_type="int8")

        # Transcribe the audio
        segments, info = model.transcribe(
            audio_path,
            language=source_lang,  # None will trigger auto-detection
            task="translate"
        )
        return segments
    except Exception as e:
        print('An error occurred during transcription:', str(e))
        return None

def format_timestamp(seconds):
    """
    Convert seconds to SRT timestamp format (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds % 1) * 1000)
    seconds = int(seconds)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def create_srt_file(segments, output_srt="captions.srt"):
    """
    Create SRT file from transcribed segments
    """
    try:
        with open(output_srt, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, start=1):
                # Convert start and end times to SRT format
                start_time = format_timestamp(segment.start)
                end_time = format_timestamp(segment.end)

                # Write SRT entry
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{segment.text.strip()}\n\n")

        return output_srt
    except Exception as e:
        print('An error occurred while creating SRT file:', str(e))
        return None

def merge_video_with_subtitles(input_video, subtitle_file, input_audio, output_video="output_with_subs.mp4"):
    """
    Merge video with SRT subtitles and audio
    """
    try:
        video = ffmpeg.input(input_video)
        audio = ffmpeg.input(input_audio)
        stream = ffmpeg.filter([video], 'subtitles', subtitle_file)
        stream = ffmpeg.output(stream, audio.audio, output_video)
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        return output_video
    except ffmpeg.Error as e:
        print('An error occurred while merging video with subtitles:', e.stderr.decode())
        return None

def process_video(input_video, input_audio):
    # Get output path
    output_video = get_output_path(input_video)

    # Check if video already exists in output directory
    if os.path.exists(output_video):
        print(f"Video already exists in output directory, skipping: {output_video}")
        return

    total_start_time = time.time()

    # 0. Start processing
    print("\n" + "=" * 50)
    print(f"Video file: {os.path.basename(input_video)}")
    print("=" * 50 + "\n")

   # 1. Extract audio
    message = "📥 Extracting audio"
    stop_event, spinner_thread = start_loading(message)
    audio_file = extract_audio(input_audio)
    elapsed_time = time.time() - total_start_time
    stop_event.set()
    spinner_thread.join()
    print(f"{message} ✅ ({elapsed_time:.1f}s)")

    # 2. Transcribe audio
    message = "🔊 Transcribing audio"
    stop_event, spinner_thread = start_loading(message)
    segments = transcribe_audio(audio_file)
    elapsed_time = time.time() - total_start_time
    stop_event.set()
    spinner_thread.join()
    print(f"{message} ✅ ({elapsed_time:.1f}s)")

    # 3. Create subtitles
    message = "📝 Creating subtitles"
    stop_event, spinner_thread = start_loading(message)
    subtitle_file = create_srt_file(segments)
    elapsed_time = time.time() - total_start_time
    stop_event.set()
    spinner_thread.join()
    print(f"{message} ✅ ({elapsed_time:.1f}s)")

    # 4. Merge video
    message = "🎬 Merging video"
    stop_event, spinner_thread = start_loading(message)
    final_video = merge_video_with_subtitles(input_video, subtitle_file, input_audio, output_video=output_video)
    elapsed_time = time.time() - total_start_time
    stop_event.set()
    spinner_thread.join()
    print(f"{message} ✅ ({elapsed_time:.1f}s)")

    # Clean up temporary files
    if audio_file and os.path.exists(audio_file):
        os.remove(audio_file)
    if subtitle_file and os.path.exists(subtitle_file):
        os.remove(subtitle_file)

    # Calculate and display total time
    total_time = time.time() - total_start_time
    minutes = int(total_time // 60)
    seconds = int(total_time % 60)

    print(f"\n✨ Completed in {minutes}m {seconds}s")
    if final_video:
        print(f"📁 Saved as: {os.path.basename(final_video)}\n")

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    videos_dir = os.path.join(current_dir, "videos")

    # Dictionary to store video-audio pairs
    video_pairs = {}

    # Loop through all files in the videos directory
    for filename in os.listdir(videos_dir):
        if filename.endswith('.mp4'):
            full_path = os.path.join(videos_dir, filename)

            # If it's an audio file
            if filename.endswith('-audio.mp4'):
                # Get base name by removing '-audio.mp4'
                base_name = filename.replace('-audio.mp4', '')
                video_pairs.setdefault(base_name, {})['audio'] = full_path
            else:
                # Get base name by removing resolution and fps info
                base_name = filename.split(' (')[0]
                video_pairs.setdefault(base_name, {})['video'] = full_path


    print(f"Found {len(video_pairs)} videos to process")


    for base_name, paths in video_pairs.items():
        if 'video' in paths and 'audio' in paths:
            process_video(paths['video'], paths['audio'])
        else:
            print(f"\nWarning: Incomplete pair for {base_name}")

if __name__=="__main__":
    main()
