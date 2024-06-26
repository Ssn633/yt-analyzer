from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import pandas as pd 
import seaborn as sns
import matplotlib.pyplot as plt
import os
import io
import base64
import pytz

# Use the Agg backend for non-GUI environments
plt.switch_backend('Agg')

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and file.filename.endswith('.json'):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Process the file
            df = pd.read_json(file_path)

            # Filter out entries from Google Ads
            df_add = df[df['details'].apply(is_from_google_ads)]
            df = df[~df['details'].apply(is_from_google_ads)]

            # Time conversion
            df['time'] = pd.to_datetime(df['time'], utc=True, format='mixed').dt.tz_convert('Asia/Kolkata')
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

            # Calculate total number of Google Ads viewed
            google_ads_count = len(df_add)
            google_ads_titles = df_add['title'].value_counts()
            max_frequency = google_ads_titles.max()
            most_repeated_ads = google_ads_titles[google_ads_titles == max_frequency].index.tolist()

            # Visualization
            custom_color = '#111827'
            # sns.set_palette(sns.color_palette([custom_color]))

            # Function to create and return base64-encoded image
            def create_plot(fig):
                buf = io.BytesIO()
                fig.savefig(buf, format='png',transparent=True )
                buf.seek(0)
                img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                buf.close()
                return img_base64

            # 1. Top Channel Bar Chart
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.barplot(x=top_channel_counts.index, y=top_channel_counts.values, ax=ax, color=custom_color)
            ax.set_title("Top 10 Channels Watched")
            ax.set_xlabel("Channel Name")
            ax.set_ylabel("Number of Videos Watched")
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            top_channel_plot = create_plot(fig)
            plt.close(fig)

            # 2. Total Time Watched Per Month Line Chart
            fig, ax = plt.subplots(figsize=(10, 6))
            total_time_per_month.plot(kind='line', marker='o', color=custom_color, ax=ax)
            ax.set_title("Total Videos Watched Per Month")
            ax.set_xlabel("Month")
            ax.set_ylabel("Total Videos Watched")
            ax.grid(True)
            total_time_per_month_plot = create_plot(fig)
            plt.close(fig)

            # 3. Total Time Watched Per Year Bar Chart
            fig, ax = plt.subplots(figsize=(10, 6))
            total_time_per_year.plot(kind='bar', color=custom_color, ax=ax)
            ax.set_title("Total Videos Watched Per Year")
            ax.set_xlabel("Year")
            ax.set_ylabel("Total Videos Watched")
            plt.xticks(rotation=0)
            total_time_per_year_plot = create_plot(fig)
            plt.close(fig)

            # 4. Watch Time Distribution by Hour
            fig, ax = plt.subplots(figsize=(10, 6))
            total_watch_hours.plot(kind='bar', color=custom_color, ax=ax)
            ax.set_title("Watch Videos Distribution by Hour")
            ax.set_xlabel("Hour of the Day")
            ax.set_ylabel("Number of Videos Watched")
            plt.xticks(rotation=0)
            total_watch_hours_plot = create_plot(fig)
            plt.close(fig)

            result = {
                'top_channel': top_channel_counts.idxmax(),
                'total_time_per_month': total_time_per_month.to_dict(),
                'total_time_per_year': total_time_per_year.to_dict(),
                'highest_watch_hour_date': str(highest_watch_hour_date),
                'total_watch_hours': total_watch_hours.to_dict(),
                'top_channel_plot': top_channel_plot,
                'total_time_per_month_plot': total_time_per_month_plot,
                'total_time_per_year_plot': total_time_per_year_plot,
                'total_watch_hours_plot': total_watch_hours_plot,
                'frequency_most_replayed': frequency_most_replayed, 
                'most_replayed_video': most_replayed_video,
                'google_ads_count': google_ads_count,
                'most_repeated_ads': most_repeated_ads,
                'max_frequency': max_frequency,
            }

            os.remove(file_path)

            return render_template('result.html', result=result)

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
