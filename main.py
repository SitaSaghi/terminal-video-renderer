import cv2
import numpy as np
import pygame
import subprocess
import os
import sys
import time



#SETTINGS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Get video path from command line
if len(sys.argv) < 2:
    print("Usage: python main.py <video_file>")
    print("Example: python main.py myvideo.mp4")
    sys.exit()

VIDEO_PATH = os.path.abspath(sys.argv[1])

# Temporary audio file
AUDIO_PATH = os.path.join(
    BASE_DIR,
    "_video_audio.wav"
)

# Higher = more detail, but slower
WIDTH = 170

# Terminal characters are taller than wide
ASPECT_CORRECTION = 0.42

# Reduce color changes for better performance
COLOR_STEP = 32

# Characters ordered roughly from dense -> light
SHADE_CHARS = "@$B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

# Edge detection sensitivity
EDGE_THRESHOLD = 140



# WINDOWS ANSI SUPPORT

os.system("")



# CHECK VIDEO

if not os.path.exists(VIDEO_PATH):

    print("Video not found:")
    print(VIDEO_PATH)

    sys.exit()



# EXTRACT AUDIO AUTOMATICALLY

def extract_audio():

    if os.path.exists(AUDIO_PATH):
        return True

    print("Extracting audio...")

    try:

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                VIDEO_PATH,
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",
                "-ac",
                "2",
                AUDIO_PATH,
            ],
            check=True,
        )

        return True

    except FileNotFoundError:

        print()
        print("FFmpeg was not found.")
        print("Install FFmpeg and make sure it is in PATH.")

        return False

    except subprocess.CalledProcessError:

        print("Could not extract audio.")

        return False



# CHARACTER SELECTION

def choose_character(
    brightness,
    gx,
    gy,
    edge_strength
):

    # Strong edge -> choose character according
    # to the direction of the edge
    if edge_strength > EDGE_THRESHOLD:

        angle = np.degrees(
            np.arctan2(gy, gx)
        )

        angle = (angle + 180) % 180

        # Gradient direction is perpendicular
        # to the visible edge.

        if angle < 22.5 or angle >= 157.5:
            return "│"

        elif angle < 67.5:
            return "/"

        elif angle < 112.5:
            return "─"

        else:
            return "\\"

    # Normal area -> brightness character

    index = int(
        brightness
        / 256
        * len(SHADE_CHARS)
    )

    index = min(
        index,
        len(SHADE_CHARS) - 1
    )

    return SHADE_CHARS[index]



# COLOR OPTIMIZATION

def quantize_color(value):

    value = int(value)

    value = (
        value // COLOR_STEP
    ) * COLOR_STEP

    return min(value, 255)



# OPEN VIDEO

cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():

    print("Could not open video.")

    sys.exit()


fps = cap.get(cv2.CAP_PROP_FPS)

if fps <= 0:
    fps = 30


total_frames = int(
    cap.get(cv2.CAP_PROP_FRAME_COUNT)
)



# AUDIO

has_audio = extract_audio()

if has_audio:

    pygame.mixer.init(
        frequency=44100
    )

    pygame.mixer.music.load(
        AUDIO_PATH
    )



# PREPARE TERMINAL

os.system("cls")

# Hide cursor
print("\033[?25l", end="")

# Clear screen
print("\033[2J", end="")

# Move cursor home
print("\033[H", end="")



# START

if has_audio:
    pygame.mixer.music.play()

start_time = time.perf_counter()

last_frame_number = -1


try:

    while True:

       
        # AUDIO/TIME IS THE MASTER CLOCK
        
        if has_audio:

            audio_ms = pygame.mixer.music.get_pos()

            if audio_ms < 0:
                break

            current_time = audio_ms / 1000.0

        else:

            current_time = (
                time.perf_counter()
                - start_time
            )


        
        # VIDEO FRAME
        
        target_frame = int(
            current_time * fps
        )


        if target_frame >= total_frames:
            break


        # If terminal is too slow, skip frames
        if target_frame <= last_frame_number:

            time.sleep(0.001)
            continue


        # Jump directly to the correct frame
        if target_frame > last_frame_number + 1:

            cap.set(
                cv2.CAP_PROP_POS_FRAMES,
                target_frame
            )


        success, frame = cap.read()

        if not success:
            break


        last_frame_number = target_frame


        
        # RESIZE
        
        original_height, original_width = (
            frame.shape[:2]
        )

        ratio = (
            original_height
            / original_width
        )

        new_height = max(
            1,
            int(
                ratio
                * WIDTH
                * ASPECT_CORRECTION
            )
        )

        frame = cv2.resize(
            frame,
            (WIDTH, new_height),
            interpolation=cv2.INTER_AREA
        )


        
        # GRAYSCALE
        
        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )


        
        # EDGE DETECTION
        
        gx = cv2.Sobel(
            gray,
            cv2.CV_32F,
            1,
            0,
            ksize=3
        )

        gy = cv2.Sobel(
            gray,
            cv2.CV_32F,
            0,
            1,
            ksize=3
        )

        magnitude = cv2.magnitude(
            gx,
            gy
        )


        
        # BUILD FRAME
        
        output = []

        for y in range(new_height):

            line = []

            previous_color = None

            for x in range(WIDTH):

                brightness = int(
                    gray[y, x]
                )

                edge_strength = (
                    magnitude[y, x]
                )

                char = choose_character(
                    brightness,
                    gx[y, x],
                    gy[y, x],
                    edge_strength
                )


                # Original color
                b, g, r = frame[y, x]


                # Reduce number of unique colors
                r = quantize_color(r)
                g = quantize_color(g)
                b = quantize_color(b)

                color = (r, g, b)


                # Only send a new ANSI color
                # command if color changed
                if color != previous_color:

                    line.append(
                        f"\033[38;2;"
                        f"{r};{g};{b}m"
                    )

                    previous_color = color


                line.append(char)


            output.append(
                "".join(line)
            )


        
        # DRAW
    
        screen = (
            "\033[H"
            + "\n".join(output)
            + "\033[0m"
        )

        sys.stdout.write(screen)

        sys.stdout.flush()


except KeyboardInterrupt:

    pass


finally:

    
    # CLEANUP
    
    cap.release()

    if has_audio:

        pygame.mixer.music.stop()
        pygame.mixer.quit()


    # Reset color
    print("\033[0m", end="")

    # Show cursor again
    print("\033[?25h", end="")

    print("\nFinished.")