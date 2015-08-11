import pandas
from sklearn.cross_validation import KFold
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.preprocessing import Normalizer, PolynomialFeatures
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.decomposition import TruncatedSVD, PCA
from utils import FEATURE_COLS, LABEL_COL, fetch_raw_data

DUMMY_VAR = 'dummy'


class ItemSelector(BaseEstimator, TransformerMixin):
    def __init__(self, key):
        self.key = key

    def fit(self, x, y=None):
        return self

    def transform(self, x, y=None):
        return x[self.key]


class Densifier(object):
    def fit(self, X, y=None):
        pass
    def fit_transform(self, X, y=None):
        return self.transform(X)
    def transform(self, X, y=None):
        return X.toarray()


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
        return (self._labels > 1000).values.ravel()


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
        ('to_dense', Densifier()),
        #  ('poly_features', PolynomialFeatures(degree=2)),
        ('truncated_svd', TruncatedSVD(n_components=100)),
        ('normalize', Normalizer()),
        #  ("model", LogisticRegression(C=10, penalty='l1')),
        ("model", RandomForestClassifier(n_estimators=100)),
        ])
    return model_pipeline


def confusion(y_true, y_pred):
    true_true = (y_true * y_pred).sum()
    false_false = ((1 - y_true) * (1 - y_pred)).sum()
    true = y_true.sum()
    false = y_true.shape[0] - true
    predict_true = y_pred.sum()
    predict_false = y_pred.shape[0] - predict_true
    print("\n")
    print("P(predict true | true) = {:,d} / {:,d} = {:.2%}".format(
        true_true, true, float(true_true) / float(true)))
    print("P(true | predict true) = {:,d} / {:,d} = {:.2%}".format(
        true_true, predict_true, float(true_true) / float(predict_true)))
    print("P(predict false | false) = {:,d} / {:,d} = {:.2%}".format(
        false_false, false, float(false_false) / float(false)))
    print("P(false | predict false) = {:,d} / {:,d} = {:.2%}".format(
        false_false, predict_false, float(false_false) / float(predict_false)))
    print("\n")


def train_model():
    features = Features()
    for train_idx, test_idx in KFold(features.features.shape[0], shuffle=True, n_folds=3):
        pipe = get_pipeline()
        pipe.fit(features.features.iloc[train_idx], features.labels[train_idx])
        confusion(features.labels[test_idx], pipe.predict(features.features.iloc[test_idx]))

if __name__ == '__main__':
    train_model()
