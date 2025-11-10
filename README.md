# RDFCon

A tool for converting tabular data to RDF

## Installation

rdfcon can be installed from github with pip, pipx, uv etc.

```bash
pip install git+https://github.com/kurrawong/rdfcon.git
```

or to install a specific version

```bash
pip install git+https://github.com/kurrawong/rdfcon.git@v1.2.0
```

## Usage

rdfcon is a command line tool that takes tabular data from `CSV` files and converts them
to `RDF` using a spec file.

To perform a conversion just run

```bash
rdfcon spec.yaml
```

where `spec.yaml` defines how the conversion should be done.

All of the configuration is done in the spec file.  
A minimal example of which could look like:

```yml
# spec.yaml

prefixes:
  - sdo: <https://schema.org/>
infile: data.csv
template: |
    <https://example.org/pid/{ID}> a sdo:CreativeWork ;
        sdo:headline "{Title}" .
```

applied over the following data

```csv
# data.csv

ID,Title
1001,Gattaca
1002,2001 a Space Odyssey
```

to produce the following RDF

```turtle
# data.ttl

@prefix sdo: <https://schema.org/> .

<https://example.org/pid/1001> a sdo:CreativeWork ;
  sdo:headline "Gattaca" ;
.

<https://example.org/pid/1002> a sdo:CreativeWork ;
  sdo:headline "2001 a Space Odyssey" ;
.
```

> [!TIP]  
> You can limit the number of rows to process with the `--limit` flag.
> very handy during testing.

> [!WARNING]  
> rdfcon currently only works with `CSV` files as input. This may be extended in a
> future release to allow other tabular formats.

### Conversion document creation

rdfcon conversion documents are just `YAML` files, so they can be created with any text
editor in the usual way.

There is also a convenient user interface that is helpful for learning the schema of the documents.

To open the ui just run

```bash
rdfcon --ui
```

And use the provided form to create your conversion document.

## Advanced usage

rdfcon provides two ways to convert data to RDF.

1. Simple column mappings

   rdfcon can map columns to RDF using simple one-to-one predicate mappings.
   These mappings can be extended in a few ways that are not
   possible with the template style mapping like splitting out multiple
   values from a single cell.

   For simple cases, this is the preferred method and will be more performant, than the
   template style mapping.

   ```yml

   ...
   identifier: id
   namespace: <https://example.org/pid/>
   types:
     - sdo:Thing
   columns:
     - column: name
       predicate: rdfs:label
     - column: description
       predicate: rdfs:comment
     - column: warehouseId
       predicate: sdo:identifier
       datatype: xsd:token
   ```

2. Turtle templates

   You can provide a turtle style template with placeholders that allows for
   greater flexibility. This method allows you to use RDF structures like blank nodes
   and to incorporate multiple columns into a single statement.

   ```yml

   ...
   template: |-
     <https://example.org/pid/{id}> a sdo:Thing ;
         rdfs:label "{name}" ;
         rdfs:comment "{description}" ;
         sdo:identifier "{warehouseId}"^^xsd:token .
   ```

The above two examples showcase an equivalent conversion using the two available
methods.

> [!NOTE]  
> The two methods are not mutually exclusive.  
> Both methods can and should be used in tandom. There are limitations to each method
> but in combination rdfcon should be able to handle most conversion scenarios.

### Custom functions

Often you just can't avoid the need for some custom logic During a conversion.
For this reason RDFCon allows you to define your own custom functions for use in
the template string. The custom functions must be written in Python, in a seperate python
file, and can be passed to the template via the `templateFunctions` parameter
in the conversion spec.

For example:

```python
# my_custom_functions.py

from datetime import datetime
import subprocess

def get_current_date() -> str:
    return datetime.today().isoformat()

def get_short_commit_hash() -> str:
    cmd = "git rev-parse --short HEAD".split()
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    short_hash = result.stdout.strip()
    return short_hash
```

```yaml
# myConversionSpec.yaml

...
templateFunctions: my_custom_functions.py
template: |
    <https://example.org/pid/{id}> a sdo:Thing ;
      sdo:comment "converted on {{ get_current_date() }} with commit {{ get_short_commit_hash() }}" ;
    .
```

For a complete example see [custom_functions.yaml](./examples/custom_functions.yaml).


### Scenarios

#### Handling different date formats

You can tell rdfcon about the format of your dates using a python date string like so:

```yml

...
columns:
  - column: someDate
    predicate: ex:date
    datatype: xsd:date
    datestr: "%d/%m/%Y"
```

This tells rdfcon that for the _someDate_ column, the values are dates like
`dd/mm/yyyy`. The date format string uses the standard [python date string
format](https://docs.python.org/3/library/datetime.html#format-codes).

If the `datestr` is provided then rdfcon will attempt to parse the values for that column
with the given format string and then convert them to ISO format datetime strings.

#### Handling cells that have multiple values in them

rdfcon can split values out from a cell if there is a consistent delimeter.

Often it is the case that you might have nested values in a cell where there are more than one
value for a column/row.

for example the following CSV file has multiple authors for a row separated by the `||`
characters

```csv
id,author
1,john||mary
2,benjamin
...
```

which can be handled in rdfcon like so

```yml

...
columns:
  - column: author
    predicate: sdo:author
    separator: "||"
```

which will convert to the following RDF statements

```turtle
<https://example.org/pid/1> sdo:author "john", "mary" .
<https://example.org/pid/2> sdo:author "benjamin" .
```

#### Normalizing a column

Commonly, you may want to generate IRIs for one of the columns in your data while
simultaneously making some statements about it.

take the following data

```csv
id,author
1,john smith
2,mandy ellis
...
```

and assume that you want to declare each of the authors as an `sdo:Person`, using the
orignal cell value as their `sdo:name`. rdfcon can handle this like so

```yml

...
columns:
  - column: author
    predicate: sdo:author
    as_iri: true
    as_uuid: true
    namespace: <https://example.org/agent/>
    type: sdo:Person
    label: sdo:name
```

which will give the following RDF

```turtle
...

<https://example.org/agent/4d413b4f-8d7e-4bcf-9d81-3914ab0a39bc> a sdo:Person ;
  sdo:name "john smith" ;
.

<https://example.org/agent/95b20cb4-c52f-497e-ac1d-3bbf030e813a> a sdo:Person ;
  sdo:name "mandy ellis" ;
.

...
```

## Further reading

A good way to explore the available options in rdfcon is to use the browser based UI.
if you haven't already, it's a good idea to run `rdfcon --ui` and explore the helpful
information on that form.

A comprehensive example is available in [examples/spec.yaml](./examples/spec.yaml). This
conversion document demonstrates all the available options and can be compared with the
accompanying data file [examples/data.csv](./examples/data.csv) and RDF output
[examples/data.trig](./examples/data.trig)

## See also

**csv2rdf**

[https://rdflib.readthedocs.io/en/stable/_modules/rdflib/tools/csv2rdf.html](https://rdflib.readthedocs.io/en/stable/_modules/rdflib/tools/csv2rdf.html)

built in to the rdflib library.

**tarql**

[https://tarql.github.io/](https://tarql.github.io/)

a sparql like conversion tool.
