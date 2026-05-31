import logging
import torch
import torchvision.transforms as T
import torch.nn.functional as F
import numpy as np
import cv2

logger = logging.getLogger(__name__)

class ReIDExtractor:
    """
    Extracts appearance features for Re-Identification.
    Uses a pretrained ResNet18 as a lightweight ReID proxy to track 
    visitors across cameras and detect re-entries.
    """
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Initializing ReID Extractor on {self.device}")
        
        # Load a pretrained ResNet18 and remove the classification head
        import torchvision.models as models
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        self.model = torch.nn.Sequential(*(list(model.children())[:-1]))
        self.model = self.model.to(self.device)
        self.model.eval()
        
        self.transform = T.Compose([
            T.ToPILImage(),
            T.Resize((256, 128)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    @torch.no_grad()
    def extract(self, frame: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
        """Extract a 512-dim embedding for a cropped bounding box."""
        x1, y1, x2, y2 = map(int, bbox)
        
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        if x2 <= x1 or y2 <= y1:
            return np.zeros(512, dtype=np.float32)
            
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return np.zeros(512, dtype=np.float32)
            
        img = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        tensor = self.transform(img).unsqueeze(0).to(self.device)
        
        features = self.model(tensor)
        features = features.view(features.size(0), -1)
        
        # L2 Normalize
        features = F.normalize(features, p=2, dim=1)
        return features.cpu().numpy().flatten()


class ReIDManager:
    """Manages the gallery of known visitors across cameras."""
    def __init__(self, threshold: float = 0.75):
        self.extractor = ReIDExtractor()
        # visitor_id -> feature vector
        self.gallery: dict[str, np.ndarray] = {}
        self.threshold = threshold
        self._next_id = 1

    def identify(self, frame: np.ndarray, bbox: tuple[int, int, int, int]) -> str:
        """Identify a person; return existing visitor_id or create a new one."""
        features = self.extractor.extract(frame, bbox)
        
        if np.all(features == 0):
            return self._create_new_visitor(features)

        best_match = None
        best_score = -1.0
        
        for visitor_id, gal_feat in self.gallery.items():
            # Cosine similarity between L2 normalized vectors is just dot product
            score = np.dot(features, gal_feat)
            if score > best_score:
                best_score = score
                best_match = visitor_id
                
        if best_score > self.threshold and best_match is not None:
            # Update gallery with moving average to adapt to appearance changes
            self.gallery[best_match] = 0.9 * self.gallery[best_match] + 0.1 * features
            self.gallery[best_match] /= np.linalg.norm(self.gallery[best_match])
            return best_match
            
        return self._create_new_visitor(features)

    def _create_new_visitor(self, features: np.ndarray) -> str:
        visitor_id = f"VIS_{self._next_id:04d}"
        self._next_id += 1
        if not np.all(features == 0):
            self.gallery[visitor_id] = features
        return visitor_id
