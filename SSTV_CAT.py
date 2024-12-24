import discord
from discord.ext import commands, tasks
from PIL import Image
import os
import serial
from datetime import datetime, timezone
import tempfile

# Replace with your bot token
TOKEN = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

# Replace with your channel ID
CHANNEL_ID = 1111111111111111111111  # Example channel ID

# Replace with the path to your BMP folder
BMP_FOLDER = 'C:\Ham\MMSSTV\History'

# Initialize the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Keep track of processed files (using modification time)
processed_files = set()


def read_yaesu_freq(port, baudrate):
    """Reads data from a Yaesu transceiver using the CAT interface."""
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            # Send a command to the transceiver (example: get frequency)
            ser.write(b"FA;\r")

            # Read the response from the transceiver
            response = ser.readline().decode("ascii").strip()
            return str(int(response[2:-1]) / 1000000) + "MHz"
    except Exception as e:
        if "could not open port" in str(e):
            return "Could not read frequency, check serial connection."
        else:
            return str(e)


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
                        jpg_file_path = os.path.join(temp_dir,
                                                    file[:-4] + ".jpg")
                        with Image.open(file_path) as img:
                            img.save(jpg_file_path, "JPEG")

                        # Get timestamp from file modification time
                        gmt_timestamp = datetime.fromtimestamp(
                            timestamp, timezone.utc).strftime(
                                "%Y-%m-%d %H:%M:%S GMT")

                        # Create the embed with frequency and timestamp
                        freq = read_yaesu_freq("COM5", 38400)
                        embed = discord.Embed(
                            description=
                            f"{freq} - {gmt_timestamp}")  # Add timestamp

                        # Send the embed with the JPG file attached
                        await channel.send(embed=embed,
                                           file=discord.File(jpg_file_path))

                    # # Move the BMP file to the "sent" subfolder
                    # sent_folder = os.path.join(BMP_FOLDER, "sent")
                    # os.makedirs(sent_folder,
                    #             exist_ok=True)  # Create the folder if it doesn't exist
                    # shutil.move(file_path, sent_folder)

                    processed_files.add(timestamp)  # Mark the file as processed

    except FileNotFoundError:
        print(f"Error: Could not find the folder '{BMP_FOLDER}'")
    except discord.HTTPException as e:
        print(f"Error sending image: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


bot.run(TOKEN)
