import logging
from html.parser import HTMLParser
import gzip

class Changer:
    """
    Changer class changes HTML text and modifies it.
    """
    def __init__(self, http_text, **kwargs):
        self.http_text = http_text  # Entire Message
        self.html_text = None  # Only HTML Part
        self.content_type = None  # Content Type - str
        self.encoding_type = None

        self.words_to_remove = None
        self.words_to_replace = None
        self.add_alert_bool = None
        if kwargs:
            if 'words_to_remove' in kwargs:
                self.words_to_remove = kwargs['words_to_remove']  # List
            if 'words_to_replace' in kwargs:
                self.words_to_replace = kwargs['words_to_replace']  # Dictionary
            if 'add_alert_bool' in kwargs:
                self.add_alert_bool = kwargs['add_alert_bool']  # Bool

        self.define_content_type()

    def set_alert_bool(self, b):
        self.add_alert_bool = b  # Bool

    def set_words_to_replace(self, dictionary):
        self.words_to_replace = dictionary  # Dictionary

    def set_words_to_remove(self, l):
        self.words_to_remove = l  # List

    def define_content_type(self):
        if self.http_text:
            try:
                subtext = self.http_text[self.http_text.index(b'Content-Type:'):]
                subtext = subtext[:subtext.index(b'\r')]
                subtext = bytes.decode(subtext)
            except ValueError as error_text:
                logging.error("No content type specified: {0}.".format(error_text))
                print(self.http_text)
            else:
                self.content_type = subtext
                logging.info("Found content type: {0}".format(self.content_type))

    def _turn_to_string(self):  # It is only called for turning http message to text
        if isinstance(self.http_text, bytes):
            try:
                self.http_text = bytes.decode(self.http_text)
            except UnicodeDecodeError:
                first_half = self.http_text[:self.http_text.index(b'\r\n\r\n') + 4]
                second_half = self.http_text[self.http_text.index(b'\r\n\r\n') + 4:]

                first_half = bytes.decode(first_half)
                second_half = bytes.decode(gzip.decompress(second_half))

                self.http_text = first_half + second_half
            except Exception as error_text:
                logging.error("Encountered Error Decoding: {0}. Returning raw data".format(error_text))

    def perform_changes(self):
        if self.http_text and self.content_type and ("text/html" in self.content_type) and \
                (self.words_to_remove or
                 self.words_to_replace or
                 self.add_alert_bool):
            logging.info("Trying to edit message...")
            try:
                self._turn_to_string()  # Turning http message to string if it isn't
                self.html_text = self.http_text[self.http_text.lower().index("<!doctype html>"):] if \
                    "<!doctype html>" in self.http_text.lower() else \
                    self.http_text[self.http_text.lower().index("<html"):]
                old_http_text = self.http_text
                old_content_length = len(self.html_text)
                parser = HtmlParser(words_to_remove=self.words_to_remove,
                                    words_to_replace=self.words_to_replace,
                                    add_alert_bool=self.add_alert_bool)
                parser.feed(self.html_text)
            except Exception:
                logging.exception(Exception)
            else:
                self.html_text = parser.get_html_text()
                self.http_text = \
                    self.http_text[:self.http_text.lower().index("<!doctype html>") - 15] + self.html_text if \
                        "<!doctype html>" in self.http_text.lower() else \
                        self.http_text[:self.http_text.lower().index("<html")] + self.html_text
                if "Content-Length:" in self.http_text:
                    self.http_text.replace("Content-Length: {0}".format(old_content_length),
                                           "Content-Length: {0}".format(len(self.html_text)))
                new_http_text = self.http_text
                if new_http_text == old_http_text:
                    print("=======")
                print("The HTTP message edited: \n{0}\n\n".format(self.http_text))
                logging.debug("Message Edited Successfully!")

    def get_http_message(self):
        http_text = self.http_text.encode() if isinstance(self.http_text, str) else self.http_text
        return http_text


class HtmlParser(HTMLParser):
    def __init__(self, **kwargs):
        super().__init__()
        self.html_text = ""

        self.words_to_remove = None
        self.words_to_replace = None
        self.add_alert_bool = False
        if kwargs:
            if 'words_to_remove' in kwargs:
                self.words_to_remove = kwargs['words_to_remove']  # List with words to remove
            if 'words_to_replace' in kwargs:
                self.words_to_replace = kwargs['words_to_replace']
                # Dictionary with words to replace and their replacement
            if 'add_alert_bool' in kwargs:
                self.add_alert_bool = kwargs['add_alert_bool']  # True or False

    def __str__(self):
        return self.html_text

    def error(self, message):
        logging.error("Encountered error while parsing HTTP message: {0}".format(message))

    def handle_starttag(self, tag, attrs):
        tag_text = "<{0} ".format(tag)
        for (attribute, value) in attrs:
            tag_text += '{0}="{1}" '.format(attribute, value)

        self.html_text += "{0}>".format(tag_text[:-1])

    def handle_startendtag(self, tag, attrs):
        tag_text = "<{0} ".format(tag)

        for (attribute, value) in attrs:
            tag_text += '{0}="{1}" '.format(attribute, value)

        self.html_text += "{0}/>".format(tag_text[:-1])

    def handle_endtag(self, tag):
        if self.add_alert_bool:
            alert_message = self.add_alert_bool.split(',')[1][2:-2]
            if tag == "head":
                self.html_text += "\n<script>alert ('{0}')</script>\n".format(alert_message)
        self.html_text += "</{0}>".format(tag)

    def handle_pi(self, data):
        self.html_text += "<?{0}>".format(data)

    def handle_data(self, data):
        words = data.split(" ")

        for index in range(len(words)):
            if self.words_to_remove:
                if words[index] in self.words_to_remove:
                    words[index] = "<strike>{0}</strike>".format(words[index])
            if self.words_to_replace:
                if words[index] in self.words_to_replace:
                    words[index] = self.words_to_replace[words[index]]

        data = " ".join(words)
        self.html_text += data

    def handle_comment(self, data):
        self.html_text += "<!--{0}-->".format(data)

    def unknown_decl(self, data):
        logging.error("Got unknown declaration while parsing HTTP message: {0}".format(data))

    def handle_decl(self, decl):
        self.html_text += "<!{0}>".format(decl)

    def get_html_text(self):
        return self.html_text


if __name__ == "__main__":
    pass
