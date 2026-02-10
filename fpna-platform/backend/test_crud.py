import requests
import json

BASE_URL = "http://localhost:8000/api/v1"


def test_crud_operations():
    """Test all CRUD operations"""

    print("=" * 60)
    print("TESTING CRUD OPERATIONS")
    print("=" * 60)

    # 1. CREATE
    print("\n1️⃣  CREATE - Adding new books...")
    books_to_create = [
        {
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "price": 42.99,
            "isbn": "978-0132350884"
        },
        {
            "title": "The Pragmatic Programmer",
            "author": "Andrew Hunt",
            "price": 39.99,
            "isbn": "978-0135957059"
        },
        {
            "title": "Anvars adventure",
            "author": "Anvar Mirzo",
            "price": 57.99,
            "isbn": "978-0158957489"
        }
    ]

    created_books = []
    for book_data in books_to_create:
        response = requests.post(f"{BASE_URL}/books/", json=book_data)
        if response.status_code == 201:
            book = response.json()
            created_books.append(book)
            print(f"   ✅ Created: {book['title']} (ID: {book['id']})")
        else:
            print(f"   ❌ Failed: {response.status_code} - {response.text}")

    # 2. READ (List)
    print("\n2️⃣  READ - Listing all books...")
    response = requests.get(f"{BASE_URL}/books/")
    if response.status_code == 200:
        books = response.json()
        print(f"   ✅ Found {len(books)} books")
        for book in books:
            print(f"      - {book['title']} by {book['author']}")
    else:
        print(f"   ❌ Failed: {response.status_code}")

    # 3. READ (Single)
    if created_books:
        book_id = created_books[0]['id']
        print(f"\n3️⃣  READ - Getting book ID {book_id}...")
        response = requests.get(f"{BASE_URL}/books/{book_id}")
        if response.status_code == 200:
            book = response.json()
            print(f"   ✅ Retrieved: {book['title']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")

    # 4. UPDATE
    if created_books:
        book_id = created_books[0]['id']
        print(f"\n4️⃣  UPDATE - Updating book ID {book_id}...")
        update_data = {
            "price": 45.99,
            "title": "Clean Code (Updated Edition)"
        }
        response = requests.put(f"{BASE_URL}/books/{book_id}", json=update_data)
        if response.status_code == 200:
            book = response.json()
            print(f"   ✅ Updated: {book['title']} - ${book['price']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")

    # 5. DELETE
    if created_books:
        book_id = created_books[-1]['id']
        print(f"\n5️⃣  DELETE - Deleting book ID {book_id}...")
        response = requests.delete(f"{BASE_URL}/books/{book_id}")
        if response.status_code == 204:
            print(f"   ✅ Deleted successfully")
        else:
            print(f"   ❌ Failed: {response.status_code}")

    # 6. Verify deletion
    print("\n6️⃣  VERIFY - Listing books after deletion...")
    response = requests.get(f"{BASE_URL}/books/")
    if response.status_code == 200:
        books = response.json()
        print(f"   ✅ Now have {len(books)} books")

    print("\n" + "=" * 60)
    print("✅ CRUD TESTS COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        test_crud_operations()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to server")
        print("   Make sure FastAPI is running: python -m app.main")
    except Exception as e:
        print(f"❌ Error: {e}")