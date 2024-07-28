from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import io
import base64

# Use the Agg backend for non-GUI environments
plt.switch_backend('Agg')

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
CHUNK_FOLDER = os.path.join(UPLOAD_FOLDER, 'chunks')
os.makedirs(CHUNK_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CHUNK_FOLDER'] = CHUNK_FOLDER

def is_from_google_ads(details):
    if isinstance(details, list):
        for item in details:
            if item.get('name') == 'From Google Ads':
                return True
    return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    chunk = request.files['chunk']
    chunk_index = request.form['chunkIndex']
    file_name = request.form['fileName']
    
    chunk_folder = os.path.join(app.config['CHUNK_FOLDER'], file_name)
    os.makedirs(chunk_folder, exist_ok=True)
    
    chunk.save(os.path.join(chunk_folder, f'{chunk_index}.part'))
    
    return 'Chunk uploaded successfully', 200

@app.route('/assemble_chunks', methods=['POST'])
def assemble_chunks():
    data = request.get_json()
    file_name = data['fileName']
    chunk_folder = os.path.join(app.config['CHUNK_FOLDER'], file_name)
    
    chunks = sorted(os.listdir(chunk_folder), key=lambda x: int(x.split('.')[0]))
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
    with open(file_path, 'wb') as output_file:
        for chunk in chunks:
            chunk_path = os.path.join(chunk_folder, chunk)
            with open(chunk_path, 'rb') as chunk_file:
                output_file.write(chunk_file.read())
    
    # Clean up chunk files after assembly
    for chunk in chunks:
        os.remove(os.path.join(chunk_folder, chunk))
    os.rmdir(chunk_folder)
    
    return jsonify({"file_path": file_path})

@app.route('/upload_success')
def upload_success():
    file_name = request.args.get('fileName')
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
    
    try:
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

        custom_color = '#111827'

        # Function to create and return base64-encoded image
        def create_plot(fig):
            buf = io.BytesIO()
            fig.savefig(buf, format='png', transparent=True)
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
        fig.patch.set_alpha(0)  # Transparent background for the figure
        ax.patch.set_alpha(0)  # Transparent background for the axes
        plt.tight_layout()
        top_channel_plot = create_plot(fig)
        plt.close(fig)

        # 2. Total Time Watched Per Month Line Chart
        fig, ax = plt.subplots(figsize=(10, 6))
        total_time_per_month = df.groupby(df['month'].astype(str)).size()
        total_time_per_month.plot(kind='line', marker='o', color=custom_color, ax=ax)
        ax.set_title("Total Videos Watched Per Month")
        ax.set_xlabel("Month")
        ax.set_ylabel("Total Videos Watched")
        ax.grid(True)
        fig.patch.set_alpha(0)  # Transparent background for the figure
        ax.patch.set_alpha(0)  # Transparent background for the axes
        total_time_per_month_plot = create_plot(fig)
        plt.close(fig)

        # 3. Total Time Watched Per Year Bar Chart
        fig, ax = plt.subplots(figsize=(10, 6))
        total_time_per_year = df.groupby(df['year']).size()
        total_time_per_year.plot(kind='bar', color=custom_color, ax=ax)
        ax.set_title("Total Videos Watched Per Year")
        ax.set_xlabel("Year")
        ax.set_ylabel("Total Videos Watched")
        plt.xticks(rotation=0)
        fig.patch.set_alpha(0)  # Transparent background for the figure
        ax.patch.set_alpha(0)  # Transparent background for the axes
        total_time_per_year_plot = create_plot(fig)
        plt.close(fig)

        # 4. Watch Time Distribution by Hour
        fig, ax = plt.subplots(figsize=(10, 6))
        total_watch_hours = df.groupby(df['hour']).size()
        total_watch_hours.plot(kind='bar', color=custom_color, ax=ax)
        ax.set_title("Watch Videos Distribution by Hour")
        ax.set_xlabel("Hour of the Day")
        ax.set_ylabel("Number of Videos Watched")
        plt.xticks(rotation=0)
        fig.patch.set_alpha(0)  # Transparent background for the figure
        ax.patch.set_alpha(0)  # Transparent background for the axes
        total_watch_hours_plot = create_plot(fig)
        plt.close(fig)

        result = {
            'top_channel': top_channel_counts.idxmax(),
            'total_time_per_month': total_time_per_month.to_dict(),
            'total_time_per_year': total_time_per_year.to_dict(),
            'highest_watch_hour_date': df['date'].value_counts().idxmax().strftime('%Y-%m-%d'),
            'frequency_most_replayed': df['title'].mode()[0],
            'most_replayed_video': df['title'].value_counts().idxmax(),
            'google_ads_count': df_add.shape[0],
            'most_repeated_ads': df_add['title'].value_counts().head(5).index.tolist(),
            'max_frequency': df_add['title'].value_counts().max(),
            'top_channel_plot': top_channel_plot,
            'total_time_per_month_plot': total_time_per_month_plot,
            'total_time_per_year_plot': total_time_per_year_plot,
            'total_watch_hours_plot': total_watch_hours_plot
        }

        return render_template('result.html', result=result)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)
