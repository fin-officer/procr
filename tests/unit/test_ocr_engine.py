"""
Unit tests for OCR engine
"""

from typing import Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

# Skip PaddleOCR tests if paddle is not available
try:
    import paddle  # noqa: F401

    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False

skip_if_paddle_not_available = pytest.mark.skipif(not PADDLE_AVAILABLE, reason="PaddlePaddle is not installed")

import cv2
import numpy as np
import pytest

from src.core.ocr_engine import EasyOCREngine, InvoiceOCREngine, PaddleOCREngine


@pytest.fixture
def sample_image():
    """Create a sample invoice image"""
    image = np.ones((800, 600, 3), dtype=np.uint8) * 255

    # Add some text-like rectangles
    cv2.rectangle(image, (50, 50), (300, 80), (0, 0, 0), -1)
    cv2.rectangle(image, (50, 100), (200, 120), (0, 0, 0), -1)
    cv2.rectangle(image, (400, 500), (550, 520), (0, 0, 0), -1)

    # Add white text on black rectangles
    cv2.putText(image, "INVOICE", (60, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(image, "Date:", (60, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(image, "Total:", (410, 515), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return image


class TestInvoiceOCREngine:
    """Test cases for InvoiceOCREngine class"""

    @pytest.fixture
    def mock_ocr_results(self):
        """Create a sample invoice image"""
        image = np.ones((800, 600, 3), dtype=np.uint8) * 255

        # Add some text-like rectangles
        cv2.rectangle(image, (50, 50), (300, 80), (0, 0, 0), -1)
        cv2.rectangle(image, (50, 100), (200, 120), (0, 0, 0), -1)
        cv2.rectangle(image, (400, 500), (550, 520), (0, 0, 0), -1)

        # Add white text on black rectangles
        cv2.putText(image, "INVOICE", (60, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(image, "Date:", (60, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(image, "Total:", (410, 515), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return image

    @pytest.fixture
    def mock_ocr_results(self):
        """Mock OCR results"""
        return [
            {"text": "INVOICE #INV-2024-001", "confidence": 0.95, "bbox": [[50, 50], [300, 50], [300, 80], [50, 80]]},
            {"text": "Date: 15.01.2024", "confidence": 0.92, "bbox": [[50, 100], [200, 100], [200, 120], [50, 120]]},
            {"text": "Test Company GmbH", "confidence": 0.88, "bbox": [[50, 150], [250, 150], [250, 170], [50, 170]]},
            {"text": "Total: €178.50", "confidence": 0.93, "bbox": [[400, 500], [550, 500], [550, 520], [400, 520]]},
        ]

    def test_ocr_engine_initialization_easyocr(self):
        """Test OCR engine initialization with EasyOCR"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader") as mock_reader:
                mock_reader.return_value = Mock()

                engine = InvoiceOCREngine(engine_type="easyocr", languages=["en", "de"])

                assert engine.engine_type == "easyocr"
                assert engine.languages == ["en", "de"]
                assert isinstance(engine.engine, EasyOCREngine)
                mock_reader.assert_called_once_with(["en", "de"], gpu=True)

    @pytest.mark.skipif(not PADDLE_AVAILABLE, reason="PaddlePaddle is not installed")
    def test_ocr_engine_initialization_paddleocr(self):
        """Test OCR engine initialization with PaddleOCR"""
        with patch("src.core.ocr_engine.PADDLEOCR_AVAILABLE", True):
            with patch("paddleocr.PaddleOCR") as mock_paddle:
                mock_paddle.return_value = Mock()
                # Also patch the PaddleOCREngine to avoid actual initialization
                with patch("src.core.ocr_engine.PaddleOCREngine") as mock_paddle_engine:
                    mock_paddle_engine.return_value = Mock()

                    engine = InvoiceOCREngine(engine_type="paddleocr", languages=["en"])

                    assert engine.engine_type == "paddleocr"
                    assert engine.languages == ["en"]
                    mock_paddle_engine.assert_called_once_with(languages=["en"])

    def test_ocr_engine_unsupported_engine(self):
        """Test OCR engine with unsupported engine type"""
        with pytest.raises(ValueError, match="Unsupported OCR engine"):
            InvoiceOCREngine(engine_type="unsupported")

    @patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True)
    @patch("src.core.ocr_engine.easyocr.Reader")
    def test_extract_invoice_text(self, mock_reader, sample_image, mock_ocr_results):
        """Test invoice text extraction"""
        # Setup mock
        mock_reader_instance = Mock()
        mock_reader_instance.readtext.return_value = [
            ([[50, 50], [300, 50], [300, 80], [50, 80]], "INVOICE #INV-2024-001", 0.95),
            ([[50, 100], [200, 100], [200, 120], [50, 120]], "Date: 15.01.2024", 0.92),
            ([[400, 500], [550, 500], [550, 520], [400, 520]], "Total: €178.50", 0.93),
        ]
        mock_reader.return_value = mock_reader_instance

        # Test extraction
        engine = InvoiceOCREngine(engine_type="easyocr")
        result = engine.extract_invoice_text(sample_image)

        assert isinstance(result, dict)
        assert "full_text" in result
        assert "text_elements" in result
        assert "structured_data" in result
        assert "total_elements" in result
        assert "avg_confidence" in result

        assert result["total_elements"] == 3
        assert result["avg_confidence"] > 0
        assert len(result["text_elements"]) == 3
        assert "INVOICE #INV-2024-001" in result["full_text"]

    def test_sort_reading_order(self):
        """Test sorting text elements in reading order"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader"):
                engine = InvoiceOCREngine(engine_type="easyocr")

                # Create unsorted text elements
                elements = [
                    {"text": "Bottom", "bbox": [[0, 200], [100, 200], [100, 220], [0, 220]], "confidence": 0.9},
                    {"text": "Top", "bbox": [[0, 50], [100, 50], [100, 70], [0, 70]], "confidence": 0.9},
                    {
                        "text": "Middle Right",
                        "bbox": [[200, 100], [300, 100], [300, 120], [200, 120]],
                        "confidence": 0.9,
                    },
                    {"text": "Middle Left", "bbox": [[0, 100], [100, 100], [100, 120], [0, 120]], "confidence": 0.9},
                ]

                sorted_elements = engine._sort_reading_order(elements)

                # Should be sorted top to bottom, left to right
                texts = [elem["text"] for elem in sorted_elements]
                expected = ["Top", "Middle Left", "Middle Right", "Bottom"]
                assert texts == expected

    def test_get_bbox_centers(self):
        """Test bounding box center calculations"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader"):
                engine = InvoiceOCREngine(engine_type="easyocr")

                # Test EasyOCR format
                easyocr_bbox = [[0, 0], [100, 0], [100, 50], [0, 50]]
                x_center = engine._get_x_center(easyocr_bbox)
                y_center = engine._get_y_center(easyocr_bbox)

                assert x_center == 50.0
                assert y_center == 25.0

                # Test standard format
                standard_bbox = [0, 0, 100, 50]
                x_center = engine._get_x_center(standard_bbox)
                y_center = engine._get_y_center(standard_bbox)

                assert x_center == 50.0
                assert y_center == 25.0

    def test_combine_text_elements(self):
        """Test combining text elements into full text"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader"):
                engine = InvoiceOCREngine(engine_type="easyocr")

                elements = [
                    {"text": "INVOICE", "bbox": [[0, 0], [100, 0], [100, 20], [0, 20]], "confidence": 0.9},
                    {"text": "Date:", "bbox": [[0, 30], [50, 30], [50, 50], [0, 50]], "confidence": 0.9},
                    {"text": "2024-01-15", "bbox": [[60, 30], [150, 30], [150, 50], [60, 50]], "confidence": 0.9},
                ]

                full_text = engine._combine_text_elements(elements)

                assert "INVOICE" in full_text
                assert "Date:" in full_text
                assert "2024-01-15" in full_text
                assert full_text.count("\n") >= 1  # Should have line breaks

    def test_structure_text_data(self):
        """Test structuring text data"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader"):
                engine = InvoiceOCREngine(engine_type="easyocr")

                elements = [
                    {"text": "INVOICE", "bbox": [[0, 0], [100, 0], [100, 20], [0, 20]], "confidence": 0.95},
                    {"text": "€123.45", "bbox": [[200, 100], [300, 100], [300, 120], [200, 120]], "confidence": 0.9},
                    {"text": "Total", "bbox": [[0, 100], [50, 100], [50, 120], [0, 120]], "confidence": 0.92},
                ]

                structured = engine._structure_text_data(elements)

                assert "lines" in structured
                assert "potential_tables" in structured
                assert "headers" in structured
                assert "amounts" in structured

                # Should detect the amount
                assert len(structured["amounts"]) >= 1

                # Should detect the header
                assert len(structured["headers"]) >= 1

    def test_is_amount_detection(self):
        """Test amount detection in text"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader"):
                engine = InvoiceOCREngine(engine_type="easyocr")

                # Test various amount formats
                assert engine._is_amount("€123.45") is True
                assert engine._is_amount("$1,234.56") is True
                assert engine._is_amount("123.45€") is True
                assert engine._is_amount("1,234.56") is True
                assert engine._is_amount("1.234,56") is True
                assert engine._is_amount("regular text") is False
                assert engine._is_amount("123") is False  # Too simple

    def test_detect_language(self):
        """Test language detection"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader"):
                engine = InvoiceOCREngine(engine_type="easyocr")

                # German text
                german_elements = [
                    {"text": "Rechnung", "confidence": 0.9},
                    {"text": "Datum", "confidence": 0.9},
                    {"text": "MwSt", "confidence": 0.9},
                    {"text": "Gesamt", "confidence": 0.9},
                ]

                language = engine.detect_language(german_elements)
                assert language == "de"

                # English text
                english_elements = [
                    {"text": "Invoice", "confidence": 0.9},
                    {"text": "Date", "confidence": 0.9},
                    {"text": "VAT", "confidence": 0.9},
                    {"text": "Total", "confidence": 0.9},
                ]

                language = engine.detect_language(english_elements)
                assert language == "en"

                # Estonian text
                estonian_elements = [
                    {"text": "Arve", "confidence": 0.9},
                    {"text": "Kuupäev", "confidence": 0.9},
                    {"text": "Käibemaks", "confidence": 0.9},
                ]

                language = engine.detect_language(estonian_elements)
                assert language == "et"

                # Unknown text (should return language with highest score, which might be 0)
                unknown_elements = [{"text": "xyz", "confidence": 0.9}, {"text": "abc", "confidence": 0.9}]

                language = engine.detect_language(unknown_elements)
                # Should return 'en' as the default language when no keywords are found
                assert language == "en"


class TestEasyOCREngine:
    """Test cases for EasyOCR engine"""

    @patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True)
    @patch("src.core.ocr_engine.easyocr.Reader")
    def test_easyocr_initialization(self, mock_reader):
        """Test EasyOCR engine initialization"""
        mock_reader.return_value = Mock()

        engine = EasyOCREngine(languages=["en", "de", "et"])

        assert engine.languages == ["en", "de", "et"]
        mock_reader.assert_called_once_with(["en", "de", "et"], gpu=True)

    def test_easyocr_not_available(self):
        """Test EasyOCR engine when not available"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", False):
            with pytest.raises(ImportError, match="EasyOCR is not installed"):
                EasyOCREngine()

    @patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True)
    @patch("src.core.ocr_engine.easyocr.Reader")
    def test_easyocr_extract_text(self, mock_reader, sample_image):
        """Test text extraction with EasyOCR"""
        mock_reader_instance = Mock()
        mock_reader_instance.readtext.return_value = [
            ([[50, 50], [300, 50], [300, 80], [50, 80]], "INVOICE", 0.95),
            ([[50, 100], [200, 100], [200, 120], [50, 120]], "Date:", 0.92),
            ([[10, 10], [20, 10], [20, 20], [10, 20]], "low", 0.2),  # Low confidence
        ]
        mock_reader.return_value = mock_reader_instance

        engine = EasyOCREngine()
        result = engine.extract_text(sample_image)

        assert len(result) == 2  # Should filter out low confidence
        assert result[0]["text"] == "INVOICE"
        assert result[0]["confidence"] == 0.95
        assert result[1]["text"] == "Date:"

    @patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True)
    @patch("src.core.ocr_engine.easyocr.Reader")
    def test_easyocr_extraction_failure(self, mock_reader, sample_image):
        """Test EasyOCR extraction failure handling"""
        mock_reader_instance = Mock()
        mock_reader_instance.readtext.side_effect = Exception("OCR failed")
        mock_reader.return_value = mock_reader_instance

        engine = EasyOCREngine()
        result = engine.extract_text(sample_image)

        assert result == []  # Should return empty list on failure


@pytest.mark.skipif(not PADDLE_AVAILABLE, reason="PaddlePaddle is not installed")
class TestPaddleOCREngine:
    """Test cases for PaddleOCR engine"""

    @patch("src.core.ocr_engine.PADDLEOCR_AVAILABLE", True)
    @patch("paddleocr.PaddleOCR")
    def test_paddleocr_initialization(self, mock_paddle):
        """Test PaddleOCR engine initialization"""
        # Mock the PaddleOCR class
        mock_ocr_instance = Mock()
        mock_ocr_instance.ocr.return_value = []
        mock_paddle.return_value = mock_ocr_instance

        engine = PaddleOCREngine(languages=["en"])

        assert engine.languages == ["en"]
        assert engine.primary_lang == "en"
        mock_paddle.assert_called_once_with(use_angle_cls=True, lang="en", use_gpu=True, show_log=False)

    def test_paddleocr_not_available(self):
        """Test PaddleOCR engine when not available"""
        with patch("src.core.ocr_engine.PADDLEOCR_AVAILABLE", False):
            with pytest.raises(ImportError, match="PaddleOCR is not installed"):
                PaddleOCREngine()

    @patch("src.core.ocr_engine.PADDLEOCR_AVAILABLE", True)
    @patch("paddleocr.PaddleOCR")
    def test_paddleocr_language_mapping(self, mock_paddle):
        """Test PaddleOCR language mapping"""
        mock_paddle.return_value = Mock()

        # Test German mapping
        engine = PaddleOCREngine(languages=["de"])
        assert engine.primary_lang == "german"

        # Test Estonian fallback to Spanish
        engine = PaddleOCREngine(languages=["et"])
        assert engine.primary_lang == "es"

    @patch("src.core.ocr_engine.PADDLEOCR_AVAILABLE", True)
    @patch("paddleocr.PaddleOCR")
    def test_paddleocr_extract_text(self, mock_paddle, sample_image):
        """Test text extraction with PaddleOCR"""
        mock_ocr_instance = Mock()
        mock_ocr_instance.ocr.return_value = [
            [
                [[[50, 50], [300, 50], [300, 80], [50, 80]], ("INVOICE", 0.95)],
                [[[50, 100], [200, 100], [200, 120], [50, 120]], ("Date:", 0.92)],
                [[[10, 10], [20, 10], [20, 20], [10, 20]], ("low", 0.2)],  # Low confidence
            ]
        ]
        mock_paddle.return_value = mock_ocr_instance

        engine = PaddleOCREngine()
        result = engine.extract_text(sample_image)

        assert len(result) == 2  # Should filter out low confidence
        assert result[0]["text"] == "INVOICE"
        assert result[0]["confidence"] == 0.95

    @patch("src.core.ocr_engine.PADDLEOCR_AVAILABLE", True)
    @patch("paddleocr.PaddleOCR")
    def test_paddleocr_empty_results(self, mock_paddle, sample_image):
        """Test PaddleOCR with empty results"""
        mock_ocr_instance = Mock()
        mock_ocr_instance.ocr.return_value = [None]  # Empty results
        mock_paddle.return_value = mock_ocr_instance

        engine = PaddleOCREngine()
        result = engine.extract_text(sample_image)

        assert result == []

    @patch("src.core.ocr_engine.PADDLEOCR_AVAILABLE", True)
    @patch("src.core.ocr_engine.PaddleOCR")
    def test_paddleocr_extraction_failure(self, mock_paddle, sample_image):
        """Test PaddleOCR extraction failure handling"""
        mock_ocr_instance = Mock()
        mock_ocr_instance.ocr.side_effect = Exception("OCR failed")
        mock_paddle.return_value = mock_ocr_instance

        engine = PaddleOCREngine()
        result = engine.extract_text(sample_image)

        assert result == []


class TestOCREngineIntegration:
    """Integration tests for OCR engine"""

    @pytest.fixture
    def sample_image(self):
        """Sample image for testing"""
        return np.ones((800, 600, 3), dtype=np.uint8) * 255

    @patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True)
    @patch("src.core.ocr_engine.easyocr.Reader")
    def test_full_invoice_processing_pipeline(self, mock_reader, sample_image):
        """Test full invoice processing pipeline"""
        # Mock comprehensive OCR results
        mock_reader_instance = Mock()
        mock_reader_instance.readtext.return_value = [
            ([[50, 50], [300, 50], [300, 80], [50, 80]], "INVOICE #INV-2024-001", 0.95),
            ([[50, 100], [200, 100], [200, 120], [50, 120]], "Date: 15.01.2024", 0.92),
            ([[50, 150], [250, 150], [250, 170], [50, 170]], "Test Company GmbH", 0.88),
            ([[50, 200], [220, 200], [220, 220], [50, 220]], "VAT ID: DE123456789", 0.90),
            ([[400, 500], [550, 500], [550, 520], [400, 520]], "Total: €178.50", 0.93),
        ]
        mock_reader.return_value = mock_reader_instance

        engine = InvoiceOCREngine(engine_type="easyocr", languages=["en", "de"])
        result = engine.extract_invoice_text(sample_image)

        # Verify comprehensive results
        assert result["total_elements"] == 5
        assert result["avg_confidence"] > 0.8

        # Check full text contains all elements
        full_text = result["full_text"]
        assert "INVOICE #INV-2024-001" in full_text
        assert "Date: 15.01.2024" in full_text
        assert "Test Company GmbH" in full_text
        assert "Total: €178.50" in full_text

        # Check structured data
        structured = result["structured_data"]
        assert len(structured["amounts"]) >= 1
        assert len(structured["lines"]) > 0

        # Verify language detection
        detected_lang = engine.detect_language(result["text_elements"])
        assert detected_lang in ["en", "de"]

    def test_performance_with_large_image(self):
        """Test OCR performance with large image"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader") as mock_reader:
                mock_reader_instance = Mock()
                mock_reader_instance.readtext.return_value = []
                mock_reader.return_value = mock_reader_instance

                engine = InvoiceOCREngine(engine_type="easyocr")

                # Create large image
                large_image = np.ones((4000, 3000, 3), dtype=np.uint8) * 255

                import time

                start_time = time.time()
                result = engine.extract_invoice_text(large_image)
                end_time = time.time()

                processing_time = end_time - start_time

                assert result is not None
                assert processing_time < 10.0  # Should complete within 10 seconds for mock

    @pytest.mark.parametrize(
        "confidence_threshold, expected_count",
        [
            (0.1, 2),  # 0.95, 0.6 > 0.3 (EasyOCR's threshold); 0.2 is filtered out
            (0.3, 2),  # 0.95, 0.6 > 0.3; 0.2 is filtered out
            (0.5, 2),  # 0.95, 0.6 > 0.5; 0.2 is filtered out
            (0.7, 1),  # 0.95 > 0.7; 0.6 is filtered; 0.2 is filtered out
            (0.9, 1),  # 0.95 > 0.9; 0.6 is filtered; 0.2 is filtered out
        ],
    )
    def test_confidence_filtering(self, confidence_threshold, expected_count):
        """Test confidence filtering with different thresholds"""
        with patch("src.core.ocr_engine.EASYOCR_AVAILABLE", True):
            with patch("src.core.ocr_engine.easyocr.Reader") as mock_reader:
                mock_reader_instance = Mock()
                mock_reader_instance.readtext.return_value = [
                    ([[0, 0], [100, 0], [100, 20], [0, 20]], "high_conf", 0.95),
                    ([[0, 30], [100, 30], [100, 50], [0, 50]], "medium_conf", 0.6),
                    ([[0, 60], [100, 60], [100, 80], [0, 80]], "low_conf", 0.2),
                ]
                mock_reader.return_value = mock_reader_instance

                # Create engine with mock
                engine = InvoiceOCREngine(engine_type="easyocr")

                # Mock the extract_text method to apply our threshold
                original_extract = engine.engine.extract_text

                def mock_extract_with_threshold(image):
                    # First apply the original extract which has the 0.3 threshold
                    results = original_extract(image)
                    # Then apply our test threshold
                    return [r for r in results if r["confidence"] > confidence_threshold]

                # Replace the extract_text method with our mock
                engine.engine.extract_text = mock_extract_with_threshold

                # Create a sample image
                sample_image = np.ones((100, 100, 3), dtype=np.uint8) * 255

                # Extract text with our mocked method
                result = engine.extract_invoice_text(sample_image)

                # Verify the number of elements matches our expectation
                assert (
                    result["total_elements"] == expected_count
                ), f"Expected {expected_count} elements with confidence > {confidence_threshold}, got {result['total_elements']}"
