import csv
from io import StringIO
import codecs

class CsvWriter(object):

    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = StringIO()
        # created a writer with Excel formating settings
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        # we ensure that we do not try to encode none or bool
        row = (x or '' for x in row)
        self.writer.writerow(row)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        # ... and reencode it into the target encoding as BytesIO
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # seek() or truncate() have side effect if not used combinated
        self.queue.truncate(0)
        self.queue.seek(0)
        # https://stackoverflow.com/questions/4330812/how-do-i-clear-a-stringio-object
        # It fails when you use self.queue = StringIO() only add one line

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
        # https://docs.python.org/3/library/io.html#io.IOBase.close
        self.queue.close()