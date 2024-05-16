import pytest
from app.infra.database_manager import DatabaseManager, DocumentEntry
from app.infra.object_store_manager import ObjectStoreManager
from app.infra.constants import *
from app.services.ml_service.constants import BLANK_NER
from app.services.ml_service.model_retrainer import ModelRetrainer

sample_text_1 = "Alice Johnson called from 212-555-1234. Her email is alice.j@example.com."
sample_tokens_1 = ["Alice", "Johnson", "called", "from", "212-555-1234", ".", "Her", "email", "is", "alice.j@example.com", "."]
sample_labels_1 = ["B-NAME", "I-NAME", "O", "O", "B-PHONE", "O", "O", "O", "O", "B-EMAIL", "O"]

sample_text_2 = "Dr. Robert Smith will see you now. His office number at 456 Elm St is 415-555-9876."
sample_tokens_2 = ["Dr.", "Robert", "Smith", "will", "see", "you", "now", ".", "His", "office", "number", "at", "456", "Elm", "St", "is", "415-555-9876", "."]
sample_labels_2 = ["O", "B-NAME", "I-NAME", "O", "O", "O", "O", "O", "O", "O", "O", "O", "B-ADDRESS", "I-ADDRESS", "I-ADDRESS", "O", "B-PHONE", "O"]

@pytest.fixture(scope="function")
def infra_manager():
    db_manager = DatabaseManager(DB_HOST, DB_USER, DB_PASS, DB_NAME)
    s3_manager = ObjectStoreManager(S3_BUCKET_NAME)

    yield db_manager, s3_manager

    db_manager.clear_table()

def test_model_retrainer_get_dataset(infra_manager):
    db_manager, s3_manager = infra_manager
    session = db_manager.Session()

    try:
        # Insert sample data into the database
        for i in range(5):
            entry1 = DocumentEntry(doc_id=None, full_text=sample_text_1, tokens=sample_tokens_1, labels=sample_labels_1, for_retrain=True)
            entry2 = DocumentEntry(doc_id=None, full_text=sample_text_2, tokens=sample_tokens_2, labels=sample_labels_2, for_retrain=True)
            session.add_all([entry1, entry2])

        session.commit()

        # Retrieve data for training
        data_entries = session.query(DocumentEntry).filter(DocumentEntry.for_retrain == True).all()
        texts = [entry.full_text for entry in data_entries]
        tokens = [entry.tokens for entry in data_entries]
        labels = [entry.labels for entry in data_entries]

        # Process the data correctly
        model_retrainer = ModelRetrainer(BLANK_NER)
        texts_train, tokens_train, labels_train, texts_test, tokens_test, labels_test = model_retrainer.split_dataset(texts, tokens, labels)
        model_retrainer.get_model(s3_manager)

        model_retrainer.retrain(texts_train, tokens_train, labels_train, 1)
        model_retrainer.evaluate(texts_test, tokens_test, labels_test)

        model_retrainer.save_and_upload_model(s3_manager)

    finally:
        session.close()  # Close session after test execution