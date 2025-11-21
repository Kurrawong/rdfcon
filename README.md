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
  sdo: <https://schema.org/>
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
> very handy during testing. run `rdfcon --help` to see all the command line flags that
> are available.

> [!WARNING]  
> rdfcon currently only works with `CSV` files as input. This may be extended in a
> future release to allow other tabular formats.

### Configuring the conversion

All RDFCon configuration is done in a `YAML` spec file.
There is a convenient user interface that is helpful for learning the schema of the documents.

To open the UI just run

```bash
rdfcon --ui
```

And use the provided form to create your spec.

After you have the knack for it, you can just create the spec files in a text
editor of your choice.

The structure of the spec file is validated against a [schema](./rdfcon/schemas.py)
before the program is run. Any issues will be raised immediately.

> [!TIP]  
> If you are having trouble with configuration, you can run `rdfcon spec.yaml -vvv` for
> very very verbose logging, which will print out the configuration as RDFCon sees it
> after it has been evaluated and processed.
>
> This is usually a good starting point for debugging any issues that come up.

## Advanced usage

RDFCon provides two ways to convert data to RDF.

1. Simple column mappings

   rdfcon can map columns to RDF using simple one-to-one predicate mappings.
   These mappings can be extended in a few ways that are not
   possible with the template style mapping like splitting out multiple
   values from a single cell.

   For simple cases, this is the preferred method and will be more performant, than the
   template style mapping.

   ```yml
   ---
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
   ---
   template: |-
     <https://example.org/pid/{id}> a sdo:Thing ;
         rdfs:label "{name}" ;
         rdfs:comment "{description}" ;
         sdo:identifier "{warehouseId}"^^xsd:token .
   ```

The above two examples will produce the same RDF.

> [!NOTE]  
> These methods are not mutually exclusive!  
> Both methods can and should be used in tandom.
> but in combination rdfcon should be able to handle most conversion scenarios.

### Custom functions

Often you will need some custom logic During a conversion.

RDFCon allows you to provide functions for use in the template string via the
`templateFunctions` parameter.

The custom functions must be written in Python, in a seperate file.

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
---
templateFunctions: my_custom_functions.py
template: |
  <https://example.org/pid/{id}> a sdo:Thing ;
    sdo:comment "converted on {{ get_current_date() }} with commit {{ get_short_commit_hash() }}" ;
  .
```

For a complete example see [custom_functions.yaml](./examples/custom_functions.yaml).

### Importing other specs

If you are writing lots of conversions you may want to re-use some parts of them.

RDFCon allows this via the imports parameter.

For example:

```yaml
# subspec.yaml
prefixes:
  ex: <https://example.org/>
  qudt: <http://qudt.org/schema/qudt/>
  unit: <http://qudt.org/vocab/unit/>
  rdfs: <http://www.w3.org/2000/01/rdf-schema#>

templateFunctions: my_custom_functions.py
```

```yaml
# spec.yaml

imports:
  - subspec.yaml

infile: mydata.csv

template: |
  ex:{id} a ex:Item ;
      rdfs:label "{name}" ;
      ex:width [
          a qudt:QuantityValue ;
          qudt:value "{distance}" ;
          qudt:unit unit:M ;
      ] ;
      rdfs:comment "Converted on {{ get_current_date() }}" ;
  .
```

The prefixes and functions from `subspec.yaml` will then be available in `spec.yaml`.

The imports parameter is a list of paths to other spec files. You can have as many as
you want and the imported spec files can also import other spec files in a recursive
manner.

The spec files are evaluated in the order they are given, with values from later imports
overwriting the values from earlier ones. In this way you can override the values from
the imported spec file.

> [!NOTE]
> For dictionary type parameters (like prefixes) the imported values will be overwritten
> key by key, meaning that rather than overwriting the whole parameter you can update and
> extend it. i.e. For the list of prefixes, you can add new ones for a specific
> conversion or overwrite one that is already defined in the imported spec.

### Scenarios

#### Handling different date formats

You can tell rdfcon about the format of your dates using a python date string like so:

```yml
---
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
---
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
---
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

#### Large files

Large input files can lead to high memory consumption, slow serialization, and
an enormous output file size. You can tell RDFCon to chunk the generated outputs
into smaller pieces. By serialing the graph into approximately sized parts.

To split the outputs into files of approximately `x` Mebibytes:

```yml
---
maxGraphSizeMb: 80
```

Which will split the outputs into files of about 80 Mb.

#### Encoding Issues

You can specify the encoding format to use with the encoding parameter.

```yml
---
encoding: utf-8-sig
```

RDFCon will use the system preferred encoding format as the default.

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

[https://rdflib.readthedocs.io/en/stable/\_modules/rdflib/tools/csv2rdf.html](https://rdflib.readthedocs.io/en/stable/_modules/rdflib/tools/csv2rdf.html)

built in to the rdflib library.

**tarql**

[https://tarql.github.io/](https://tarql.github.io/)

a sparql like conversion tool.
