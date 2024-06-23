from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
import pandas as pd 
import seaborn as sns
import matplotlib.pyplot as plt
import os
import json
import pytz
import threading
import time

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = './static/results'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

def delete_old_files():
    while True:
        try:
            now = time.time()
            for filename in os.listdir(app.config['RESULT_FOLDER']):
                file_path = os.path.join(app.config['RESULT_FOLDER'], filename)
                if os.path.isfile(file_path):
                    # Get file creation time
                    creation_time = os.path.getctime(file_path)
                    # Check if file is older than 5 minutes
                    if (now - creation_time) > (5 * 60):  # 5 minutes = 5 * 60 seconds
                        os.remove(file_path)
                        # print(f"Deleted old file: {filename}")
        except Exception as e:
            print()
            # print(f"Error deleting old files: {e}")
        time.sleep(300)  # Sleep for 5 minutes (300 seconds)

# Start background thread for deleting old files
delete_thread = threading.Thread(target=delete_old_files)
delete_thread.daemon = True
delete_thread.start()

def is_from_google_ads(details):
    if isinstance(details, list):
        for item in details:
            if item.get('name') == 'From Google Ads':
                return True
    return False


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=["POST", "GET"])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Process the file
        df = pd.read_json(file_path)

        # Filter out entries from Google Ads
        df = df[~df['details'].apply(is_from_google_ads)]

        # Time conversion
        df['time'] = pd.to_datetime(df['time'], utc=True).dt.tz_convert('Asia/Kolkata')
        df['date'] = df['time'].dt.date
        df['hour'] = df['time'].dt.hour
        df['month'] = df['time'].dt.to_period('M')
        df['year'] = df['time'].dt.year

        # Analysis
        top_channel_counts = df['subtitles'].apply(lambda x: x[0]['name'] if isinstance(x, list) else None).value_counts().head(10)
        total_time_per_month = df.groupby('month').size()
        total_time_per_year = df.groupby('year').size()
        highest_watch_hour_date = df.groupby('date').size().idxmax()
        total_watch_hours = df['hour'].value_counts().sort_index()
        frequency_most_replayed = df['title'].value_counts().max()
        most_replayed_video = df['title'].value_counts().idxmax() 
        
        # Visualization
        color_palette = sns.color_palette("viridis", as_cmap=True)

        # 1. Top Channel Bar Chart
        plt.figure(figsize=(10, 6))
        sns.barplot(x=top_channel_counts.index, y=top_channel_counts.values)
        plt.title("Top 10 Channels Watched")
        plt.xlabel("Channel Name")
        plt.ylabel("Number of Videos Watched")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        top_channel_plot_path = os.path.join(app.config['RESULT_FOLDER'], 'top_channel_plot.png')
        plt.savefig(top_channel_plot_path)
        plt.close()

        # 2. Total Time Watched Per Month Line Chart
        plt.figure(figsize=(10, 6))
        total_time_per_month.plot(kind='line', marker='o', color=color_palette(0.5))
        plt.title("Total Videos Watched Per Month")
        plt.xlabel("Month")
        plt.ylabel("Total Videos Watched")
        plt.grid(True)
        total_time_per_month_plot_path = os.path.join(app.config['RESULT_FOLDER'], 'total_time_per_month_plot.png')
        plt.savefig(total_time_per_month_plot_path)
        plt.close()

        # 3. Total Time Watched Per Year Bar Chart
        plt.figure(figsize=(10, 6))
        total_time_per_year.plot(kind='bar', color=color_palette(0.5))
        plt.title("Total Videos Watched Per Year")
        plt.xlabel("Year")
        plt.ylabel("Total Videos Watched")
        plt.xticks(rotation=0)
        total_time_per_year_plot_path = os.path.join(app.config['RESULT_FOLDER'], 'total_time_per_year_plot.png')
        plt.savefig(total_time_per_year_plot_path)
        plt.close()

        # 4. Watch Time Distribution by Hour
        plt.figure(figsize=(10, 6))
        total_watch_hours.plot(kind='bar', color=color_palette(0.5))
        plt.title("Watch Videos Distribution by Hour")
        plt.xlabel("Hour of the Day")
        plt.ylabel("Number of Videos Watched")
        plt.xticks(rotation=0)
        total_watch_hours_plot_path = os.path.join(app.config['RESULT_FOLDER'], 'total_watch_hours_plot.png')
        plt.savefig(total_watch_hours_plot_path)
        plt.close()

        result = {
            'top_channel': top_channel_counts.idxmax(),
            'total_time_per_month': total_time_per_month.to_dict(),
            'total_time_per_year': total_time_per_year.to_dict(),
            'highest_watch_hour_date': str(highest_watch_hour_date),
            'total_watch_hours': total_watch_hours.to_dict(),
            'top_channel_plot_path': top_channel_plot_path,
            'total_time_per_month_plot_path': total_time_per_month_plot_path,
            'total_time_per_year_plot_path': total_time_per_year_plot_path,
            'total_watch_hours_plot_path': total_watch_hours_plot_path,
            'frequency_most_replayed': frequency_most_replayed, 
            'most_replayed_video': most_replayed_video,
            
        }

        os.remove(file_path)

        return render_template('result.html', result=result)

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)