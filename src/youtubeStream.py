import asyncio
import cv2
import time

from typing import ClassVar, Dict, Mapping, Optional, Any, Tuple, List
from typing_extensions import Self
from yt_dlp import YoutubeDL

from viam.components.camera import Camera
from viam.logging import getLogger
from viam.media.video import ViamImage, Optional, CameraMimeType, NamedImage
from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResponseMetadata
from viam.resource.base import ResourceBase, ResourceName
from viam.resource.types import Model, ModelFamily
from viam.utils import struct_to_dict

LOGGER = getLogger(__name__)

class youtubeStream(Camera, Reconfigurable):
    
    """
    Camera represents any physical hardware that can capture frames.
    """
    video_url: str
    default_url: str = "https://www.youtube.com/watch?v=MusSS4R9SPw"

    MODEL: ClassVar[Model] = Model(ModelFamily("julie", "livestream"), "youtube-stream")
    REQUIRED_ATTRIBUTES: ClassVar[List[str]] = ["video_url"]
    

    # Constructor
    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        my_stream = cls(config.name)
        my_stream.reconfigure(config, dependencies)
        return my_stream
    
    def __init__(self, name: str):
        super().__init__(name)
        self.video_cap: Optional [cv2.VideoCapture] = None

    # Validates JSON Configuration
    @classmethod
    def validate(cls, config: ComponentConfig):
        # Here we validate config, the following is just an example and should be updated as needed
        is_missing_attrs = [attr for attr in cls.REQUIRED_ATTRIBUTES if attr not in config.attributes]
        if is_missing_attrs:
            LOGGER.error("Missing required attributes in Youtube stream Configuration.")
            raise ValueError(f"Missing required attributes in Youtube stream Configuration: {', '.join(is_missing_attrs)}")
        return
    
    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        LOGGER.info("Reconfiguring " + self.name)
        attrs = struct_to_dict(config.attributes)
        self.video_url = str(attrs.get("video_url", self.default_url))

        self.config = config
        self.dependencies = dependencies

        # Release the previous video capture object
        if self.video_cap:
            self.video_cap.release()

        # Fetch the actual video URL using yt_dlp
        stream_url = self.get_video_url(self.video_url)

        # Init. the video capture object with the fetched stream URL
        self.video_cap = cv2.VideoCapture(stream_url)
    
    def get_video_url(self, youtube_url: str) -> str:
        # Fetch the direct video URL from YouTube using yt_dlp.
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }
        ydl = YoutubeDL(ydl_opts)
        try:
            info = ydl.extract_info(youtube_url, download=False)
            stream_url = info['url']
            LOGGER.info(f"Fetched video stream URL: {stream_url}")
            return stream_url
        except Exception as e:
            LOGGER.error(f"Error fetching video stream URL: {e}")
            raise RuntimeError("Failed to fetch the YouTube stream URL.")
        
    async def get_image(self, mime_type: str = "", *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs) -> ViamImage:
        # Check if video capture is initialized
        if self.video_cap is None:
            raise RuntimeError("Video capture is not initialized.")

        for _ in range(5):  # Retry getting the video capture up to 5 times
            ret, frame = self.video_cap.read()
            if ret:
                break
            await asyncio.sleep(1)  # Wait 1 second before retrying 
        if not ret:
            raise RuntimeError("Failed to capture any frame from the video.")
                
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            raise RuntimeError("Failed to encode frame as JPEG.")
        
        image_data = jpeg.tobytes()
        return ViamImage(image_data, CameraMimeType.JPEG)
    
    async def get_images(self, *, timeout: Optional[float] = None, **kwargs) -> Tuple[List[NamedImage], ResponseMetadata]:
        raise NotImplementedError()

    async def get_point_cloud(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs
    ) -> Tuple[bytes, str]:
        raise NotImplementedError()
        
    async def get_properties(self, *, timeout: Optional[float] = None, **kwargs) -> 'Camera.Properties':
        return Camera.Properties(
        mime_types=['image/jpeg']  
    )
