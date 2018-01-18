# closeenough
A Simple Synonym and similar word searching python flask app using wordnet and glove datasets

#### Dependencies

Closeenough is written using python 2 and depends on the following

- [flask](http://flask.pocoo.org/)
- [annoy](https://github.com/spotify/annoy)
- [nltk](http://www.nltk.org/)
- [wordnet for nltk](http://www.nltk.org/howto/wordnet.html)

#### Getting started
##### Clone/download this repo
```shell
git clone https://github.com/yasiruk/closeenough.git
```

##### Dependency Installation

Install the python dependencies
```shell
pip install flask annoy nltk
```

Install wordnet corpus for NLTK
```shell
python -m nltk.downloader wordnet
```

#### Usage

##### Quick Start

Running the following command will download all necessary glove data sets, build indexes and start the server
```shell
python closeenough.py --init
```
##### Configuration

Closeenough can be configured to use a preexisiting glove data set and annoy files as follows:
```shell
python closeenough.py <glove data file location> <annoy index file location> <http port>
```
The following will start the app in HTTP port 9000 and use glove.6B.txt glove data set file. 
```shell
python closeenough.py glove.6B.txt glove.6B.ann 9000

```