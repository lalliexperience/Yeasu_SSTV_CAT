import discord
from discord.ext import commands, tasks
from PIL import Image
import os
import serial
from datetime import datetime, timezone
import tempfile

# Replace with your bot token
TOKEN = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'


# Replace with your channel ID
CHANNEL_ID = 1111111111111111  # Example channel ID

# Replace with the path to your BMP folder
BMP_FOLDER = 'C:\Ham\MMSSTV\History'

# Initialize the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Keep track of processed files (using modification time)
processed_files = set()

def read_yaesu_freq(port, baudrate):
    """Reads data from a Yaesu transceiver using the CAT interface.
    
    Returns:
        A tuple containing the frequency (in MHz) and the mode as a string.
    """

    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            # Send a command to the transceiver to get frequency and mode
            ser.write(b"IF;\r") 

            # Read the response from the transceiver
            response = ser.readline().decode("ascii").strip()
            print("Radio response: " + response)
            
            freq = int(response[2:-14])/1000000
            mode_code = response[21:-6]
            
            # Dictionary to map mode codes to mode names
            mode_dict = {
                "1": "LSB", "2": "USB", "3": "CW-U", "4": "FM", "5": "AM",
                "6": "RTTY-L", "7": "CW-L", "8": "DATA-L", "9": "RTTY-U",
                "A": "DATA-FM", "B": "FM-N", "C": "DATA-U", "D": "AM-N",
                "F": "D-FM-N", "E": "PSK"
            }
            
            mode = mode_dict.get(mode_code, "Unknown Mode")  # Get mode name or "Unknown Mode"

            return freq, mode
    except serial.SerialException as e:
        return f"Could not read frequency, check serial connection: {e}", "N/A"
    except Exception as e:
        return f"An error occurred: {e}", "N/A"


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

    # Get initial list of files on startup (using modification time)
    global processed_files
    for file in os.listdir(BMP_FOLDER):
        if file.endswith(".bmp"):
            file_path = os.path.join(BMP_FOLDER, file)
            processed_files.add(os.path.getmtime(file_path))

    monitor_folder.start()


@tasks.loop(seconds=5)  # Check every 5 seconds
async def monitor_folder():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("Error: Could not find the specified channel.")
        return

    try:
        # Get the list of files in the folder
        files = os.listdir(BMP_FOLDER)

        for file in files:
            if file.endswith(".bmp"):
                file_path = os.path.join(BMP_FOLDER, file)
                timestamp = os.path.getmtime(file_path)

                if timestamp not in processed_files:
                    print(file)

                    # Create a temporary directory
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Convert BMP to JPG and store in the temporary directory
                        jpg_file_path = os.path.join(temp_dir, file[:-4] + ".jpg")
                        with Image.open(file_path) as img:
                            img.save(jpg_file_path, "JPEG")

                        # Get timestamp from file modification time
                        gmt_timestamp = datetime.fromtimestamp(
                            timestamp, timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")

                        # Get frequency and mode from the transceiver
                        freq, mode = read_yaesu_freq("COM5", 38400) 

                        # Create the embed with frequency, mode, and timestamp
                        embed = discord.Embed(description=f"{freq} MHz - {mode} - {gmt_timestamp}")

                        # Send the embed with the JPG file attached
                        await channel.send(embed=embed, file=discord.File(jpg_file_path))

                    processed_files.add(timestamp)  # Mark the file as processed

    except FileNotFoundError:
        print(f"Error: Could not find the folder '{BMP_FOLDER}'")
    except discord.HTTPException as e:
        print(f"Error sending image: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


bot.run(TOKEN)
