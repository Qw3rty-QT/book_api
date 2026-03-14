import io
import json
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, ImageTk


DEFAULT_API_URL = "http://127.0.0.1:5000/books"
THUMBNAIL_SIZE = (72, 104)
PREVIEW_SIZE = (240, 340)


@dataclass
class Book:
	book_id: int
	title: str
	author: str
	price: float | str
	image_url: str


class BookApiClient:
	def __init__(self, api_url: str) -> None:
		self.api_url = api_url

	def fetch_books(self) -> list[Book]:
		try:
			with urlopen(self.api_url, timeout=10) as response:
				payload = json.load(response)
		except HTTPError as error:
			raise RuntimeError(f"API returned HTTP {error.code}") from error
		except URLError as error:
			raise RuntimeError("Cannot connect to Book API. Start book.py first.") from error

		books = payload.get("books", [])
		return [
			Book(
				book_id=book.get("id", 0),
				title=book.get("title", ""),
				author=book.get("author", ""),
				price=book.get("price", "-"),
				image_url=book.get("image_url", ""),
			)
			for book in books
		]


class BookDesktopApp:
	def __init__(self, root: tk.Tk, api_client: BookApiClient) -> None:
		self.root = root
		self.api_client = api_client
		self.books: list[Book] = []
		self.tree_book_map: dict[str, Book] = {}
		self.image_bytes_cache: dict[str, bytes] = {}
		self.thumbnail_cache: dict[str, ImageTk.PhotoImage] = {}
		self.preview_cache: dict[str, ImageTk.PhotoImage] = {}
		self.search_var = tk.StringVar()
		self.status_var = tk.StringVar(value="Ready")
		self.preview_title_var = tk.StringVar(value="Select a book")
		self.preview_author_var = tk.StringVar(value="Author: -")
		self.preview_price_var = tk.StringVar(value="Price: -")
		self.preview_url_var = tk.StringVar(value="Image URL: -")

		self.root.title("Book API Desktop App")
		self.root.geometry("1360x700")
		self.root.minsize(1100, 560)

		self._configure_styles()
		self.placeholder_thumbnail = self._create_placeholder_image(THUMBNAIL_SIZE)
		self.placeholder_preview = self._create_placeholder_image(PREVIEW_SIZE)
		self._build_layout()
		self.search_var.trace_add("write", self._handle_search_change)
		self.refresh_books()

	def _configure_styles(self) -> None:
		style = ttk.Style(self.root)
		style.configure("BookGrid.Treeview", rowheight=112)
		style.configure("BookTitle.TLabel", font=("Segoe UI", 16, "bold"))

	def _build_layout(self) -> None:
		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(1, weight=1)

		header = ttk.Frame(self.root, padding=(16, 16, 16, 8))
		header.grid(row=0, column=0, sticky="ew")
		header.columnconfigure(0, weight=1)
		header.columnconfigure(1, weight=0)

		title_label = ttk.Label(
			header,
			text="Book Catalog",
			font=("Segoe UI", 18, "bold"),
		)
		title_label.grid(row=0, column=0, sticky="w")

		subtitle_label = ttk.Label(
			header,
			text=f"Source: {self.api_client.api_url}",
		)
		subtitle_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

		refresh_button = ttk.Button(header, text="Refresh", command=self.refresh_books)
		refresh_button.grid(row=0, column=1, rowspan=2, sticky="e")

		search_frame = ttk.Frame(header)
		search_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
		search_frame.columnconfigure(1, weight=1)

		search_label = ttk.Label(search_frame, text="Search")
		search_label.grid(row=0, column=0, sticky="w", padx=(0, 8))

		search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
		search_entry.grid(row=0, column=1, sticky="ew")
		search_entry.bind("<Escape>", self._clear_search)

		clear_button = ttk.Button(search_frame, text="Clear", command=lambda: self.search_var.set(""))
		clear_button.grid(row=0, column=2, sticky="e", padx=(8, 0))

		content = ttk.Frame(self.root, padding=(16, 8, 16, 8))
		content.grid(row=1, column=0, sticky="nsew")
		content.columnconfigure(0, weight=3)
		content.columnconfigure(1, weight=2)
		content.rowconfigure(0, weight=1)

		grid_frame = ttk.Frame(content)
		grid_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
		grid_frame.columnconfigure(0, weight=1)
		grid_frame.rowconfigure(0, weight=1)

		columns = ("id", "title", "author", "price")
		self.tree = ttk.Treeview(
			grid_frame,
			columns=columns,
			show="tree headings",
			height=16,
			style="BookGrid.Treeview",
		)
		self.tree.heading("#0", text="Cover")
		self.tree.heading("id", text="ID")
		self.tree.heading("title", text="Title")
		self.tree.heading("author", text="Author")
		self.tree.heading("price", text="Price (USD)")

		self.tree.column("#0", width=90, anchor="center", stretch=False)
		self.tree.column("id", width=70, anchor="center", stretch=False)
		self.tree.column("title", width=360, anchor="w")
		self.tree.column("author", width=200, anchor="w")
		self.tree.column("price", width=100, anchor="e", stretch=False)

		vertical_scrollbar = ttk.Scrollbar(grid_frame, orient="vertical", command=self.tree.yview)
		horizontal_scrollbar = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.tree.xview)
		self.tree.configure(yscrollcommand=vertical_scrollbar.set, xscrollcommand=horizontal_scrollbar.set)
		self.tree.bind("<<TreeviewSelect>>", self._handle_selection)

		self.tree.grid(row=0, column=0, sticky="nsew")
		vertical_scrollbar.grid(row=0, column=1, sticky="ns")
		horizontal_scrollbar.grid(row=1, column=0, sticky="ew")

		detail_frame = ttk.LabelFrame(content, text="Book Details", padding=(16, 16, 16, 16))
		detail_frame.grid(row=0, column=1, sticky="nsew")
		detail_frame.columnconfigure(0, weight=1)

		self.preview_label = ttk.Label(detail_frame, image=self.placeholder_preview, anchor="center")
		self.preview_label.grid(row=0, column=0, sticky="n", pady=(0, 16))
		self.preview_label.image = self.placeholder_preview

		title_value = ttk.Label(
			detail_frame,
			textvariable=self.preview_title_var,
			style="BookTitle.TLabel",
			wraplength=320,
			justify="left",
		)
		title_value.grid(row=1, column=0, sticky="w")

		author_value = ttk.Label(
			detail_frame,
			textvariable=self.preview_author_var,
			wraplength=320,
			justify="left",
		)
		author_value.grid(row=2, column=0, sticky="w", pady=(12, 0))

		price_value = ttk.Label(detail_frame, textvariable=self.preview_price_var)
		price_value.grid(row=3, column=0, sticky="w", pady=(8, 0))

		url_value = ttk.Label(
			detail_frame,
			textvariable=self.preview_url_var,
			wraplength=320,
			justify="left",
		)
		url_value.grid(row=4, column=0, sticky="w", pady=(12, 0))

		status_bar = ttk.Label(
			self.root,
			textvariable=self.status_var,
			padding=(16, 8, 16, 16),
			anchor="w",
		)
		status_bar.grid(row=2, column=0, sticky="ew")

	def refresh_books(self) -> None:
		self.status_var.set("Loading books...")
		self.root.update_idletasks()

		try:
			self.books = self.api_client.fetch_books()
		except RuntimeError as error:
			self.status_var.set(str(error))
			messagebox.showerror("Book API Error", str(error))
			return

		self._render_books()

	def _render_books(self) -> None:
		for item_id in self.tree.get_children():
			self.tree.delete(item_id)

		self.tree_book_map.clear()
		query = self.search_var.get().strip().lower()

		filtered_books = [
			book
			for book in self.books
			if not query
			or query in book.title.lower()
			or query in book.author.lower()
			or query in str(book.book_id)
		]

		for book in filtered_books:
			thumbnail = self._get_book_image(book.image_url, THUMBNAIL_SIZE, self.thumbnail_cache, self.placeholder_thumbnail)
			item_id = self.tree.insert(
				"",
				"end",
				text="",
				image=thumbnail,
				values=(book.book_id, book.title, book.author, self._format_price(book.price)),
			)
			self.tree_book_map[item_id] = book

		if filtered_books:
			first_item_id = self.tree.get_children()[0]
			self.tree.selection_set(first_item_id)
			self.tree.focus(first_item_id)
			self._show_book_details(filtered_books[0])
		else:
			self._clear_book_details()

		self.status_var.set(f"Showing {len(filtered_books)} of {len(self.books)} books")

	def _handle_search_change(self, *_args: object) -> None:
		self._render_books()

	def _clear_search(self, _event: tk.Event) -> str | None:
		self.search_var.set("")
		return "break"

	def _handle_selection(self, _event: tk.Event) -> None:
		selection = self.tree.selection()
		if not selection:
			return

		selected_book = self.tree_book_map.get(selection[0])
		if selected_book is not None:
			self._show_book_details(selected_book)

	def _show_book_details(self, book: Book) -> None:
		preview = self._get_book_image(book.image_url, PREVIEW_SIZE, self.preview_cache, self.placeholder_preview)
		self.preview_label.configure(image=preview)
		self.preview_label.image = preview
		self.preview_title_var.set(book.title or "-")
		self.preview_author_var.set(f"Author: {book.author or '-'}")
		self.preview_price_var.set(f"Price: {self._format_price(book.price)} USD")
		self.preview_url_var.set(f"Image URL: {book.image_url or '-'}")

	def _clear_book_details(self) -> None:
		self.preview_label.configure(image=self.placeholder_preview)
		self.preview_label.image = self.placeholder_preview
		self.preview_title_var.set("No books found")
		self.preview_author_var.set("Author: -")
		self.preview_price_var.set("Price: -")
		self.preview_url_var.set("Image URL: -")

	def _get_book_image(
		self,
		image_url: str,
		size: tuple[int, int],
		cache: dict[str, ImageTk.PhotoImage],
		placeholder: ImageTk.PhotoImage,
	) -> ImageTk.PhotoImage:
		if not image_url:
			return placeholder

		if image_url in cache:
			return cache[image_url]

		try:
			image_bytes = self._fetch_image_bytes(image_url)
			with Image.open(io.BytesIO(image_bytes)) as image:
				prepared_image = ImageOps.contain(image.convert("RGB"), size)
				canvas = Image.new("RGB", size, "#f3f4f6")
				x_offset = (size[0] - prepared_image.width) // 2
				y_offset = (size[1] - prepared_image.height) // 2
				canvas.paste(prepared_image, (x_offset, y_offset))
		except (HTTPError, URLError, OSError, ValueError):
			cache[image_url] = placeholder
			return placeholder

		cache[image_url] = ImageTk.PhotoImage(canvas)
		return cache[image_url]

	def _fetch_image_bytes(self, image_url: str) -> bytes:
		if image_url not in self.image_bytes_cache:
			request = Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
			with urlopen(request, timeout=15) as response:
				self.image_bytes_cache[image_url] = response.read()
		return self.image_bytes_cache[image_url]

	def _create_placeholder_image(self, size: tuple[int, int]) -> ImageTk.PhotoImage:
		placeholder = Image.new("RGB", size, "#d1d5db")
		return ImageTk.PhotoImage(placeholder)

	def _format_price(self, price: float | str) -> str:
		if isinstance(price, (int, float)):
			return f"{float(price):.2f}"
		return str(price)


def main() -> None:
	root = tk.Tk()
	BookDesktopApp(root, BookApiClient(DEFAULT_API_URL))

	root.mainloop()


if __name__ == "__main__":
	main()