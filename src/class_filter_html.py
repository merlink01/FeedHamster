import htmllib
import formatter
from formatter import *
import StringIO
#~ import web

def extract_text(html, threshold):
    # http://ai-depot.com/articles/the-easy-way-to-extract-useful-text-from-arbitrary-html/#more-90
    print "threshold",threshold
    # Derive from formatter.AbstractWriter to store paragraphs.
    writer = LineWriter(threshold = threshold)
    # Default formatter sends commands to our writer.
    formatter = AbstractFormatter(writer)
    # Derive from htmllib.HTMLParser to track parsed bytes.
    parser = TrackingParser(writer, formatter)
    # Give the parser the raw HTML data.
    parser.feed(html)
    parser.close()
    # Filter the paragraphs stored and output them.
    print writer.output()
    return writer.output()


class TrackingParser(htmllib.HTMLParser):
    """Try to keep accurate pointer of parsing location."""
    def __init__(self, writer, *args):
        htmllib.HTMLParser.__init__(self, *args)
        self.writer = writer
    def parse_starttag(self, i):
        index = htmllib.HTMLParser.parse_starttag(self, i)
        self.writer.index = index
        return index
    def parse_endtag(self, i):
        self.writer.index = i
        return htmllib.HTMLParser.parse_endtag(self, i)

class Paragraph:
    def __init__(self):
        self.text = ''
        self.bytes = 0
        self.density = 0.0

class LineWriter(formatter.AbstractWriter):
    def __init__(self, threshold, *args):
        self.last_index = 0
        self.lines = [Paragraph()]
        formatter.AbstractWriter.__init__(self)
        self.threshold = threshold

    def send_flowing_data(self, data):
        # Work out the length of this text chunk.
        t = len(data)
        # We've parsed more text, so increment index.
        self.index += t
        # Calculate the number of bytes since last time.
        b = self.index - self.last_index
        self.last_index = self.index
        # Accumulate this information in current line.
        l = self.lines[-1]
        l.text += data
        l.bytes += b

    def send_paragraph(self, blankline):
        """Create a new paragraph if necessary."""
        if self.lines[-1].text == '':
            return
        self.lines[-1].text += '<BR/>' * (blankline+1)#'<BR/>' hier wird ein \r oder \n gesetzt
        self.lines[-1].bytes += 2 * (blankline+1)
        self.lines.append(Paragraph())

    def send_literal_data(self, data):
        self.send_flowing_data(data)

    def send_line_break(self):
        self.send_paragraph(0)
    def compute_density(self):
        """Calculate the density for each line, and the average."""
        total = 0.0
        for l in self.lines:
            try:l.density = len(l.text) / float(l.bytes)
            except:pass
            total += l.density
        # Store for optional use by the neural network.
        self.average = total / float(len(self.lines))

    def output(self):
        """Return a string with the useless lines filtered out."""
        self.compute_density()
        output = StringIO.StringIO()
        for l in self.lines:
            # Check density against threshold.
            # Custom filter extensions go here.
            if l.density > self.threshold:
                # print "found:",l.text
                output.write(l.text)
        return output.getvalue()

#~ und dann aufrufen:
html = extract_text("<test>htmlstring, very long</test>",100)
print 'x',html,'x'
#~ html = web.utils.safestr(html, encoding='utf-8')

#~ und hier die gefragte filter funktion, die ich vorher aufrufe:
def filter_html(html="""<test>htmlstring, very long</test>"""):
    # alles filtern was vor und nach dem html tag kommt
    regex = r"(?i)(<html>[\s\S]+?</html>)"
    # regex = r"(?i)(<head>[\s\S]+</body>)"
    try:
        html = re.findall(regex,html)[0]
    except:pass
        # log.warning("<head> regex not found")
    # html = html[0]

    #filter head
    regex = r"(?i)(<head>[\s\S]+?</head>)"
    html = re.sub(regex," ",html)#[0]

    #filter alles was kommentar ist
    regex = r"(?i)(<!--[\s\S]+?-->)"
    html = re.sub(regex," ",html)#[0]

    #filter alles was script ist
    regex = r"(?i)(<script[\s\S]+?/script>)"
    html = re.sub(regex," ",html)#[0]

    #filter alles was noscript ist
    regex = r"(?i)(<noscript[\s\S]+?/noscript>)"
    html = re.sub(regex," ",html)#[0]

    #filter alles was iframe ist
    regex = r"(?i)(<iframe[\s\S]+?/iframe>)"
    html = re.sub(regex," ",html)#[0]

    return html 
    
    
