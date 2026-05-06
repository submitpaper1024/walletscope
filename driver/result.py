def check_file_for_keywords(file_path):
    target_words = ["suspicious", "scam", "warning", "phishing"]
    found_words = set()

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line_lower = line.lower()
                for word in target_words:
                    if word in line_lower:
                        found_words.add(word)
        if found_words:
            print("warning:yes")
            print(f"words: {', '.join(found_words)}")
        else:
            print("no warning")
    except FileNotFoundError:
        print(f"not found the file '{file_path}'")
    except Exception as e:
        print(f"error: {e}")


if __name__ == "__main__":
    check_file_for_keywords("Rabby Wallet_pagesource.txt")
