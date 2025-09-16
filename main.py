import os
import requests
import streamlit as st
from dotenv import load_dotenv
from convert import download_mp3_bytes

load_dotenv()
api_key = os.getenv("YOUTUBE_API_KEY")

st.set_page_config(page_title="YouTube MP3 Downloader", page_icon="🎵", layout="wide")
st.title("Mp3YT")

if not api_key:
    st.error("YOUTUBE_API_KEY is not set. Define it in .env or the environment.")
    st.stop()

with st.form("search_form"):
    query = st.text_input("Search YouTube", placeholder="search for music....")
    submitted = st.form_submit_button("Search")

if submitted and query:
    # Store search results in session state to persist across reruns
    st.session_state['search_results'] = None
    st.session_state['search_query'] = query
    
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 10,
        "key": api_key,
    }
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        st.session_state['search_results'] = data.get("items", [])
    except requests.RequestException as e:
        st.error(f"Search failed: {e}")
        st.session_state['search_results'] = []

# Display results from session state if available
if 'search_results' in st.session_state and st.session_state['search_results'] is not None:
    items = st.session_state['search_results']
    if not items:
        st.info("No results found.")
    else:
        st.success(f"Found {len(items)} results for: {st.session_state.get('search_query', 'your search')}")
        
        for item in items:
            vid = item["id"]["videoId"]
            title = item["snippet"]["title"]
            url = f"https://www.youtube.com/watch?v={vid}"

            with st.container():
                st.subheader(title)
                cols = st.columns([2, 1])
                with cols[0]:
                    st.video(url)
                with cols[1]:
                    key_bytes = f"mp3_bytes_{vid}"
                    key_name = f"mp3_name_{vid}"
                    key_converting = f"converting_{vid}"

                    # Show conversion status
                    if st.session_state.get(key_converting, False):
                        st.info("Converting... Please wait")
                        st.spinner("Converting to MP3...")
                        
                    if st.button("Convert to MP3", key=f"convert_{vid}", disabled=st.session_state.get(key_converting, False)):
                        st.session_state[key_converting] = True
                        try:
                            with st.status("Converting to MP3...", expanded=True) as status:
                                st.write("Downloading audio...")
                                fname, data = download_mp3_bytes(url)
                                st.write("Conversion complete!")
                                status.update(label="Conversion complete!", state="complete")
                                
                            st.session_state[key_bytes] = data
                            st.session_state[key_name] = fname
                            st.session_state[key_converting] = False
                            st.success("MP3 ready! Use the download button below.")
                            st.rerun()
                        except Exception as e:
                            st.session_state[key_converting] = False
                            st.error(f"Conversion failed: {str(e)}")
                            # Log the full error for debugging
                            st.write("Error details:", str(e))

                    if key_bytes in st.session_state and key_name in st.session_state:
                        st.download_button(
                            "📥 Download MP3",
                            data=st.session_state[key_bytes],
                            file_name=st.session_state[key_name],
                            mime="audio/mpeg",
                            key=f"dl_{vid}",
                        )
                st.divider()