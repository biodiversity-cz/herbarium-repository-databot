import requests
import xml.etree.ElementTree as ET

class CetafSidService:

    NAMESPACES = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'dc': 'http://purl.org/dc/terms/',
        'dwc': 'http://rs.tdwg.org/dwc/terms/',
        'owl': 'http://www.w3.org/2002/07/owl#'
    }

    PROPERTIES = [
        ('dc', 'title'),
        ('dc', 'description'),
        ('dc', 'creator'),
        ('dc', 'created'),
        ('dc', 'publisher'),
        ('dc', 'thumbnail'),
        # DwC
        ('dwc', 'materialSampleID'),
        ('dwc', 'basisOfRecord'),
        ('dwc', 'collectionCode'),
        ('dwc', 'catalogNumber'),
        ('dwc', 'scientificName'),
        ('dwc', 'previousIdentifications'),
        ('dwc', 'family'),
        ('dwc', 'genus'),
        ('dwc', 'specificEpithet'),
        ('dwc', 'country'),
        ('dwc', 'countryCode'),
        ('dwc', 'locality'),
        ('dwc', 'eventDate'),
        ('dwc', 'recordNumber'),
        ('dwc', 'recordedBy'),
        ('dwc', 'fieldNumber'),
        ('dwc', 'associatedMedia'),
        ('dwc', 'iri')
    ]

    def fetch_sid_as_dict(self, url: str) -> dict:
        """
        Fetch CETSF SID RDF/XML from URL, follow redirects,
        and return a dictionary where keys are full RDF URIs.
        Also attaches owl:sameAs values to the original property if present.
        """
        headers = {"Accept": "application/rdf+xml"}
        try:
            response = requests.get(url, headers=headers, allow_redirects=True)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch data from {url}: {e}")

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            raise Exception(f"Failed to parse XML from {url}: {e}")

        data = {}

        for prefix, tag in self.PROPERTIES:
            full_uri = self.NAMESPACES[prefix] + tag
            element = root.find(f'.//{prefix}:{tag}', self.NAMESPACES)
            if element is not None:
                value = element.text
                # Pokud je owl:sameAs u tohoto elementu
                same_as_elem = element.find('owl:sameAs', self.NAMESPACES)
                if same_as_elem is not None:
                    resource = same_as_elem.attrib.get(f'{{{self.NAMESPACES["rdf"]}}}resource')
                    if resource:
                        # uložíme jako tuple: (hodnota, sameAs)
                        data[full_uri] = (value, resource)
                        continue
                data[full_uri] = value

        return data
