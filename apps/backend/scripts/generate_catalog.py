"""Generate catalog.csv with 100+ entries and required edge cases."""

import csv
from pathlib import Path

rows: list[dict] = []


def add(i: int, title: str, author: str, alt: str = "", edition: str = "") -> None:
    rows.append(
        {
            "id": i,
            "title": title,
            "author": author,
            "alternate_titles": alt,
            "edition_info": edition,
        }
    )


# Edge cases (explicit)
add(1, "Pride and Prejudice", "Jane Austen", "", "1813 first edition")
add(2, "Pride and Prejudice", "Jane Austen", "", "Annotated Norton Critical Edition")
add(
    3,
    "Harry Potter and the Sorcerer's Stone",
    "J.K. Rowling",
    "Harry Potter and the Philosopher's Stone",
    "US edition",
)
add(
    4,
    "Harry Potter and the Philosopher's Stone",
    "Joanne Rowling",
    "Harry Potter and the Sorcerer's Stone",
    "UK edition",
)
add(5, "The Road", "Cormac McCarthy")
add(6, "The Road", "Jack London")
add(7, "The Lord of the Rings", "J.R.R. Tolkien", "LOTR omnibus", "Omnibus one-volume")
add(8, "The Fellowship of the Ring", "J.R.R. Tolkien", "", "Volume 1")
add(9, "The Two Towers", "J.R.R. Tolkien", "", "Volume 2")
add(10, "The Return of the King", "J.R.R. Tolkien", "", "Volume 3")
add(11, "The Great Gatsby", "F. Scott Fitzgerald")
add(12, "Great", "Sara Benincasa")
add(13, "The Hobbit", "J.R.R. Tolkien")
add(14, "The Hobbit", "Tolkien, J.R.R.", "", "Deluxe reprint")
add(15, "The Hobbit", "John Ronald Reuel Tolkien", "", "Illustrated edition")

books = [
    ("1984", "George Orwell"),
    ("Animal Farm", "George Orwell"),
    ("To Kill a Mockingbird", "Harper Lee"),
    ("The Catcher in the Rye", "J.D. Salinger"),
    ("Lord of the Flies", "William Golding"),
    ("Brave New World", "Aldous Huxley"),
    ("Fahrenheit 451", "Ray Bradbury"),
    ("The Handmaid's Tale", "Margaret Atwood"),
    ("Dune", "Frank Herbert"),
    ("Foundation", "Isaac Asimov"),
    ("Neuromancer", "William Gibson"),
    ("Snow Crash", "Neal Stephenson"),
    ("The Name of the Wind", "Patrick Rothfuss"),
    ("The Wise Man's Fear", "Patrick Rothfuss"),
    ("A Game of Thrones", "George R.R. Martin"),
    ("A Clash of Kings", "George R.R. Martin"),
    ("The Way of Kings", "Brandon Sanderson"),
    ("Words of Radiance", "Brandon Sanderson"),
    ("The Silent Patient", "Alex Michaelides"),
    ("Gone Girl", "Gillian Flynn"),
    ("The Girl on the Train", "Paula Hawkins"),
    ("The Da Vinci Code", "Dan Brown"),
    ("Angels and Demons", "Dan Brown"),
    ("The Alchemist", "Paulo Coelho"),
    ("Life of Pi", "Yann Martel"),
    ("The Kite Runner", "Khaled Hosseini"),
    ("A Thousand Splendid Suns", "Khaled Hosseini"),
    ("The Book Thief", "Markus Zusak"),
    ("All the Light We Cannot See", "Anthony Doerr"),
    ("The Nightingale", "Kristin Hannah"),
    ("Where the Crawdads Sing", "Delia Owens"),
    ("Educated", "Tara Westover"),
    ("Becoming", "Michelle Obama"),
    ("Sapiens", "Yuval Noah Harari"),
    ("Atomic Habits", "James Clear"),
    ("The Subtle Art of Not Giving a F*ck", "Mark Manson"),
    ("Thinking, Fast and Slow", "Daniel Kahneman"),
    ("Quiet", "Susan Cain"),
    ("The Power of Habit", "Charles Duhigg"),
    ("Outliers", "Malcolm Gladwell"),
    ("Blink", "Malcolm Gladwell"),
    ("The Tipping Point", "Malcolm Gladwell"),
    ("Freakonomics", "Steven Levitt"),
    ("The Immortal Life of Henrietta Lacks", "Rebecca Skloot"),
    ("The Martian", "Andy Weir"),
    ("Project Hail Mary", "Andy Weir"),
    ("Ready Player One", "Ernest Cline"),
    ("Ender's Game", "Orson Scott Card"),
    ("The Hunger Games", "Suzanne Collins"),
    ("Catching Fire", "Suzanne Collins"),
    ("Mockingjay", "Suzanne Collins"),
    ("Twilight", "Stephenie Meyer"),
    ("The Fault in Our Stars", "John Green"),
    ("Looking for Alaska", "John Green"),
    ("It", "Stephen King"),
    ("The Shining", "Stephen King"),
    ("Misery", "Stephen King"),
    ("Carrie", "Stephen King"),
    ("The Stand", "Stephen King"),
    ("Dracula", "Bram Stoker"),
    ("Frankenstein", "Mary Shelley"),
    ("Jane Eyre", "Charlotte Bronte"),
    ("Wuthering Heights", "Emily Bronte"),
    ("Moby-Dick", "Herman Melville"),
    ("The Odyssey", "Homer"),
    ("The Iliad", "Homer"),
    ("Crime and Punishment", "Fyodor Dostoevsky"),
    ("The Brothers Karamazov", "Fyodor Dostoevsky"),
    ("War and Peace", "Leo Tolstoy"),
    ("Anna Karenina", "Leo Tolstoy"),
    ("One Hundred Years of Solitude", "Gabriel Garcia Marquez"),
    ("Love in the Time of Cholera", "Gabriel Garcia Marquez"),
    ("The Stranger", "Albert Camus"),
    ("The Plague", "Albert Camus"),
    ("Beloved", "Toni Morrison"),
    ("The Color Purple", "Alice Walker"),
    ("Invisible Man", "Ralph Ellison"),
    ("The Sun Also Rises", "Ernest Hemingway"),
    ("For Whom the Bell Tolls", "Ernest Hemingway"),
    ("A Farewell to Arms", "Ernest Hemingway"),
    ("The Old Man and the Sea", "Ernest Hemingway"),
    ("Slaughterhouse-Five", "Kurt Vonnegut"),
    ("Cat's Cradle", "Kurt Vonnegut"),
    ("Catch-22", "Joseph Heller"),
    ("The Grapes of Wrath", "John Steinbeck"),
    ("Of Mice and Men", "John Steinbeck"),
    ("East of Eden", "John Steinbeck"),
    ("The Picture of Dorian Gray", "Oscar Wilde"),
    ("Dr Jekyll and Mr Hyde", "Robert Louis Stevenson"),
    ("Treasure Island", "Robert Louis Stevenson"),
    ("The Adventures of Sherlock Holmes", "Arthur Conan Doyle"),
    ("The Hound of the Baskervilles", "Arthur Conan Doyle"),
    ("The Count of Monte Cristo", "Alexandre Dumas"),
    ("Les Miserables", "Victor Hugo"),
    ("The Hunchback of Notre-Dame", "Victor Hugo"),
    ("Don Quixote", "Miguel de Cervantes"),
    ("The Divine Comedy", "Dante Alighieri"),
    ("Paradise Lost", "John Milton"),
    ("The Canterbury Tales", "Geoffrey Chaucer"),
    ("Hamlet", "William Shakespeare"),
    ("Macbeth", "William Shakespeare"),
    ("Romeo and Juliet", "William Shakespeare"),
    ("Othello", "William Shakespeare"),
    ("King Lear", "William Shakespeare"),
    ("The Tempest", "William Shakespeare"),
    ("A Midsummer Night's Dream", "William Shakespeare"),
    ("The Prince", "Niccolo Machiavelli"),
    ("Meditations", "Marcus Aurelius"),
    ("The Art of War", "Sun Tzu"),
]

next_id = 16
for title, author in books:
    add(next_id, title, author)
    next_id += 1

add(next_id, "Harry Potter and the Chamber of Secrets", "J.K. Rowling", "", "US")
next_id += 1
add(next_id, "Harry Potter and the Prisoner of Azkaban", "Rowling, J.K.", "", "UK")
next_id += 1
add(next_id, "Norwegian Wood", "Haruki Murakami", "Norwegian Wood: Tokyo Blues", "US title")
next_id += 1
add(next_id, "Norwegian Wood: Tokyo Blues", "Haruki Murakami", "Norwegian Wood", "UK title")
next_id += 1
add(next_id, "The Lion, the Witch and the Wardrobe", "C.S. Lewis", "", "Chronicles vol 1")
next_id += 1
add(next_id, "A Wizard of Earthsea", "Ursula K. Le Guin")

out = Path(__file__).resolve().parent.parent / "catalog.csv"
with out.open("w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(
        fh, fieldnames=["id", "title", "author", "alternate_titles", "edition_info"]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} catalog entries to {out}")
