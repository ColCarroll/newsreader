import pandas
import numpy
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.preprocessing import Normalizer, PolynomialFeatures
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import ElasticNet
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.grid_search import GridSearchCV
from sklearn.decomposition import TruncatedSVD
from utils import FEATURE_COLS, LABEL_COL, fetch_raw_data

DUMMY_VAR = 'dummy'


class ItemSelector(BaseEstimator, TransformerMixin):
    def __init__(self, key):
        self.key = key

    def fit(self, x, y=None):
        return self

    def transform(self, x, y=None):
        return x[self.key]


class Features(object):
    def __init__(self):
        self._features = None
        self._labels = None

    def _get_features_and_labels(self):
        data = pandas.DataFrame(fetch_raw_data())
        self._labels = data[[LABEL_COL]]
        self._features = data[FEATURE_COLS]
        return data

    @property
    def features(self):
        if self._features is None:
            self._get_features_and_labels()
        return self._features

    @property
    def labels(self):
        if self._labels is None:
            self._get_features_and_labels()
        return numpy.log1p(self._labels)


def get_pipeline():
    title_pipeline = Pipeline([
        ("prepare", ItemSelector("title")),
        ("tfidf", TfidfVectorizer(stop_words='english', lowercase=True, use_idf=True)),
        ])

    domain_pipeline = Pipeline([
        ("prepare", ItemSelector("domain")),
        ("to_vect", CountVectorizer(min_df=10))
        ])

    subreddit_pipeline = Pipeline([
        ("prepare", ItemSelector("subreddit")),
        ("to_vect", CountVectorizer(min_df=10))
        ])

    model_pipeline = Pipeline([
        ("merge", FeatureUnion(transformer_list=[
            ("domain", domain_pipeline),
            ("subreddit", subreddit_pipeline),
            ("title", title_pipeline)])),
        ('truncated_svd', TruncatedSVD(n_components=100)),
        ('poly_features', PolynomialFeatures(degree=2)),
        ('normalize', Normalizer()),
        ("model", ElasticNet())
        ])

    parameters = {
        "model__alpha": [1, 3, 10],
    }
    return model_pipeline, parameters


def train_model():
    pipe, params = get_pipeline()
    grid_search = GridSearchCV(pipe, params, n_jobs=-1, verbose=1)
    features = Features()
    grid_search.fit(features.features, features.labels)
    print("Best score: %0.3f" % grid_search.best_score_)
    print("Best parameters set:")
    best_parameters = grid_search.best_estimator_.get_params()
    for param_name in sorted(params.keys()):
        print("\t%s: %r" % (param_name, best_parameters[param_name]))


if __name__ == '__main__':
    train_model()
