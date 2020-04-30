#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2014-2019 CNRS

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# AUTHORS
# Rachid RIAD
"""
##########
Dissimilarity
##########

"""
from abc import ABCMeta, abstractmethod
from functools import lru_cache
from typing import List, Optional, Union, Tuple, Any, Callable

import numpy as np
from matplotlib import pyplot as plt
from pyannote.core import Segment
from similarity.weighted_levenshtein import CharacterSubstitutionInterface
from similarity.weighted_levenshtein import WeightedLevenshtein

from pygamma.continuum import Annotator

Unit = Tuple[Annotator, Segment]


class AbstractDissimilarity(metaclass=ABCMeta):

    def __init__(self,
                 annotation_task: str,
                 DELTA_EMPTY: float):
        self.annotation_task = annotation_task
        self.DELTA_EMPTY = DELTA_EMPTY

    @abstractmethod
    def __getitem__(self, units: Tuple[Any, Any]) -> float:
        pass

    def batch_compute(self, batch: Any) -> np.ndarray:
        pass


class CategoricalDissimilarity(AbstractDissimilarity):
    """Categorical Dissimilarity
    Parameters
    ----------
    annotation_task :
        task to be annotated
    list_categories :
        list of categories
    categorical_dissimilarity_matrix :
        Dissimilarity matrix to compute
    DELTA_EMPTY :
        empty dissimilarity value
    function_cat :
        Function to adjust dissimilarity based on categorical matrix values
    Returns
    -------
    dissimilarity : Dissimilarity
        Dissimilarity
    """

    def __init__(self,
                 annotation_task: str,
                 list_categories: List[str],
                 categorical_dissimilarity_matrix: Optional[np.ndarray] = None,
                 DELTA_EMPTY: float = 1,
                 function_cat: Optional[Callable[[float], float]] = None):
        super().__init__(annotation_task, DELTA_EMPTY)

        self.list_categories = list_categories
        self.function_cat = function_cat
        assert len(list_categories) == len(set(list_categories))
        self.num_categories = len(self.list_categories)
        self.dict_list_categories = dict(zip(self.list_categories,
                                             range(self.num_categories)))
        self.categorical_dissimilarity_matrix = categorical_dissimilarity_matrix
        if self.categorical_dissimilarity_matrix is None:
            # building the default dissimilarity matrix
            self.categorical_dissimilarity_matrix = np.ones(
                (self.num_categories, self.num_categories)) - np.eye(
                self.num_categories)
        else:
            # sanity checks on the categorical_dissimilarity_matrix
            assert isinstance(self.categorical_dissimilarity_matrix, np.ndarray)
            assert np.all(self.categorical_dissimilarity_matrix <= 1)
            assert np.all(0 <= self.categorical_dissimilarity_matrix)
            assert np.all(self.categorical_dissimilarity_matrix ==
                          categorical_dissimilarity_matrix.T)

    def plot_categorical_dissimilarity_matrix(self):
        fig, ax = plt.subplots()
        im = plt.imshow(
            self.categorical_dissimilarity_matrix,
            extent=[0, self.num_categories, 0, self.num_categories])
        ax.figure.colorbar(im, ax=ax)
        plt.xticks([el + 0.5 for el in range(self.num_categories)],
                   self.list_categories)
        plt.yticks([el + 0.5 for el in range(self.num_categories)],
                   self.list_categories[::-1])
        plt.setp(
            ax.get_xticklabels(),
            rotation=45,
            ha="right",
            rotation_mode="anchor")
        ax.xaxis.set_ticks_position('top')
        plt.show()

    @lru_cache(maxsize=None)
    def __getitem__(self, units: Tuple[str, str]):
        # assert type(units) == list
        if len(units) < 2:
            return self.DELTA_EMPTY
        else:
            assert units[0] in self.list_categories
            assert units[1] in self.list_categories
            cat_dis = self.categorical_dissimilarity_matrix[
                self.dict_list_categories[units[0]]][self.dict_list_categories[units[1]]]
            if self.function_cat is not None:
                cat_dis = self.function_cat(cat_dis)

            return cat_dis * self.DELTA_EMPTY

    def batch_compute(self, units: List[Tuple[str, str]]) -> np.ndarray:
        # embedding all categories (first as list, then coverting to array)
        cat_embds_list = []
        for cat_a, cat_b in units:
            cat_embds_list.append((self.dict_list_categories[cat_a],
                                   self.dict_list_categories[cat_b]))
        cat_embds = np.array(cat_embds_list).swapaxes(0, 1)
        # retrieving all the distances
        cat_dists = self.categorical_dissimilarity_matrix[cat_embds[0],
                                                          cat_embds[1]]
        cat_dists *= cat_dists * self.DELTA_EMPTY
        if self.function_cat is None:
            return cat_dists
        else:
            return np.array([self.function_cat(d) for d in cat_dists])


class SequenceDissimilarity(AbstractDissimilarity):
    """Sequence Dissimilarity
    Parameters
    ----------
    annotation_task :
        task to be annotated
    list_admitted_symbols :
        list of admitted symbols in the sequence
    categorical_symbol_dissimlarity_matrix :
        Dissimilarity matrix to compute between symbols
    DELTA_EMPTY :
        empty dissimilarity value
    function_cat :
        Function to adjust dissimilarity based on categorical matrix values
    Returns
    -------
    dissimilarity : Dissimilarity
        Dissimilarity
    """

    class CharacterSubstitution(CharacterSubstitutionInterface):
        def __init__(self, list_admitted_symbols, dict_list_symbols,
                     symbol_dissimilarity_matrix):
            super().__init__()
            self.list_admitted_symbols = list_admitted_symbols
            self.dict_list_symbols = dict_list_symbols
            self.symbol_dissimilarity_matrix = symbol_dissimilarity_matrix

        def cost(self, c0, c1):
            return self.symbol_dissimilarity_matrix[self.dict_list_symbols[
                c0]][self.dict_list_symbols[c1]]

    def __init__(self,
                 annotation_task,
                 list_admitted_symbols,
                 symbol_dissimlarity_matrix=None,
                 DELTA_EMPTY=1,
                 function_cat=lambda x: x):
        super().__init__(annotation_task, DELTA_EMPTY)

        self.function_cat = function_cat
        self.admitted_symbols_set = set(list_admitted_symbols)
        assert len(list_admitted_symbols) == len(self.admitted_symbols_set)
        self.num_symbols = len(self.admitted_symbols_set)
        self.dict_list_symbols = dict(zip(self.admitted_symbols_set,
                                          range(self.num_symbols)))
        self.symbol_dissimilarity_matrix = symbol_dissimlarity_matrix
        if self.symbol_dissimilarity_matrix is None:
            self.symbol_dissimilarity_matrix = np.ones(
                (self.num_symbols, self.num_symbols)) - np.eye(
                self.num_symbols)
        else:
            assert type(self.symbol_dissimilarity_matrix) == np.ndarray
            assert np.all(self.symbol_dissimilarity_matrix <= 1)
            assert np.all(0 <= self.symbol_dissimilarity_matrix)
            assert np.all(self.symbol_dissimilarity_matrix ==
                          symbol_dissimlarity_matrix.T)

    def plot_symbol_dissimilarity_matrix(self):
        fig, ax = plt.subplots()
        im = plt.imshow(
            self.symbol_dissimilarity_matrix,
            extent=[0, self.num_symbols, 0, self.num_symbols])
        ax.figure.colorbar(im, ax=ax)
        plt.xticks([el + 0.5 for el in range(self.num_symbols)],
                   self.admitted_symbols_set)
        plt.yticks([el + 0.5 for el in range(self.num_symbols)],
                   self.admitted_symbols_set[::-1])
        plt.setp(
            ax.get_xticklabels(),
            rotation=45,
            ha="right",
            rotation_mode="anchor")
        ax.xaxis.set_ticks_position('top')
        plt.show()

    @lru_cache(maxsize=None)
    def __getitem__(self, units: Tuple[str, str]):

        weighted_levenshtein = WeightedLevenshtein(
            self.CharacterSubstitution(self.admitted_symbols_set,
                                       self.dict_list_symbols,
                                       self.symbol_dissimilarity_matrix)
        )

        # assert type(units) == list
        if len(units) < 2:
            return self.DELTA_EMPTY
        else:
            assert set(units[0]) <= self.admitted_symbols_set
            assert set(units[1]) <= self.admitted_symbols_set
            return self.function_cat(
                weighted_levenshtein.distance(units[0], units[1]) / max(
                    len(units[0]), len(units[1]))) * self.DELTA_EMPTY


class PositionalDissimilarity(AbstractDissimilarity):
    """Positional Dissimilarity
    Parameters
    ----------
    annotation_task :
        task to be annotated
    DELTA_EMPTY :
        empty dissimilarity value
    function_distance :
        position function difference
    Returns
    -------
    dissimilarity : Dissimilarity
        Dissimilarity
    """

    def __init__(self, annotation_task, DELTA_EMPTY=1, function_distance=None):
        super().__init__(annotation_task, DELTA_EMPTY)
        self.function_distance = function_distance

    @lru_cache(maxsize=None)
    def __getitem__(self, units: List[Segment]):
        # assert type(units) == list
        if len(units) < 2:
            return self.DELTA_EMPTY
        elif len(units) == 2:
            if self.function_distance is None:
                # triple indexing to tracks in pyannote
                # DANGER if the api breaks
                first, second = units
                distance_pos = (np.abs(first.start - second.start) +
                                np.abs(first.end - second.end))
                distance_pos /= (first.duration + second.duration)
                distance_pos = distance_pos * distance_pos * self.DELTA_EMPTY
                return distance_pos

    def batch_compute(self, batch: List[Tuple[Segment, Segment]]) -> np.ndarray:
        first_row_boundaries_list = []
        second_row_boundaries_list = []
        for first_seg, second_seg in batch:
            first_row_boundaries_list.append((first_seg.start,
                                              first_seg.end))
            second_row_boundaries_list.append((second_seg.start,
                                               second_seg.end))
        first_row_bounds = np.array(first_row_boundaries_list).swapaxes(0, 1)
        second_row_bounds = np.array(second_row_boundaries_list).swapaxes(0, 1)
        starts_diffs = np.abs(first_row_bounds[0] - second_row_bounds[0])
        ends_diffs = np.abs(first_row_bounds[1] - second_row_bounds[1])
        durations_sum = ((first_row_bounds[1] - first_row_bounds[0]) +
                         (second_row_bounds[1] - second_row_bounds[0]))
        distance_pos = (starts_diffs + ends_diffs) / durations_sum
        distance_pos = distance_pos * distance_pos * self.DELTA_EMPTY
        return distance_pos


class AbstractCombinedDissimilarity(AbstractDissimilarity):

    def __init__(self,
                 annotation_task: str,
                 DELTA_EMPTY: float,
                 alpha: float,
                 beta: float,
                 positional_dissimilarity: PositionalDissimilarity,
                 annotation_dissimilarity: Union[CategoricalDissimilarity,
                                                 SequenceDissimilarity]):
        super().__init__(annotation_task, DELTA_EMPTY)
        self.alpha, self.beta = alpha, beta
        self.positional_dissim = positional_dissimilarity
        self.annotation_dissim = annotation_dissimilarity

    @lru_cache(maxsize=None)
    def __getitem__(self, units: Tuple[Tuple[Segment, Segment],
                                       Tuple[str, str]]):
        timing_units, annot_units = units
        # sanity check
        assert len(timing_units) == len(annot_units)
        if len(timing_units) < 2:
            return self.DELTA_EMPTY
        else:
            dis = self.alpha * self.positional_dissim[timing_units]
            dis += self.beta * self.annotation_dissim[annot_units]
            return dis

    def batch_compute(self, batch: Tuple[List[Tuple[Segment, Segment]],
                                         List[Tuple[str, str]]]) -> np.ndarray:
        all_timings, all_annots = batch
        assert len(all_annots) == len(all_timings)
        timing_dists = self.positional_dissim.batch_compute(all_timings)
        annot_dists = self.annotation_dissim.batch_compute(all_annots)
        return timing_dists * self.alpha + annot_dists * self.beta



class CombinedCategoricalDissimilarity(AbstractCombinedDissimilarity):
    # TODO : update this doc, it does not match the __init__ signature
    """Combined Dissimilarity
    Parameters
    ----------
    annotation_task :
        task to be annotated
    list_categories :
        list of categories
    categorical_dissimilarity_matrix :
        Dissimilarity matrix to compute
    function_cat :
        Function to adjust dissimilarity based on categorical matrix values
    DELTA_EMPTY :
        empty dissimilarity value
    function_distance :
        position function difference
    Returns
    -------
    dissimilarity : Dissimilarity
        Dissimilarity
    """

    def __init__(self,
                 annotation_task: str,
                 list_categories: List[str],
                 alpha: int = 3,
                 beta: int = 1,
                 DELTA_EMPTY: float = 1,
                 function_distance=None,
                 categorical_dissimilarity_matrix=None,
                 function_cat=lambda x: x):
        #  building child positional and categorical dissimilarities objs
        positional_dissimilarity = PositionalDissimilarity(
            annotation_task=annotation_task,
            DELTA_EMPTY=DELTA_EMPTY,
            function_distance=function_distance)

        categorical_dissimilarity = CategoricalDissimilarity(
            annotation_task=annotation_task,
            list_categories=list_categories,
            categorical_dissimilarity_matrix=categorical_dissimilarity_matrix,
            DELTA_EMPTY=DELTA_EMPTY,
            function_cat=function_cat)

        super().__init__(annotation_task, DELTA_EMPTY, alpha, beta,
                         positional_dissimilarity,
                         categorical_dissimilarity)


class CombinedSequenceDissimilarity(AbstractCombinedDissimilarity):
    """Combined Sequence Dissimilarity
    Parameters
    ----------
    annotation_task :
        task to be annotated
    list_admitted_symbols :
        list of admitted symbols in the sequence
    symbol_dissimilarity_matrix :
        Dissimilarity matrix to compute between symbols
    function_cat :
        Function to adjust dissimilarity based on categorical matrix values
    DELTA_EMPTY :
        empty dissimilarity value
    f_dis :
        position function difference
    Returns
    -------
    dissimilarity : Dissimilarity
        Dissimilarity
    """

    def __init__(self,
                 annotation_task: str,
                 list_admitted_symbols: List[str],
                 alpha: int = 3,
                 beta: int = 1,
                 DELTA_EMPTY: int = 1,
                 function_distance=None,
                 symbol_dissimilarity_matrix=None,
                 function_cat=lambda x: x):
        positional_dissimilarity = PositionalDissimilarity(
            annotation_task=annotation_task,
            DELTA_EMPTY=DELTA_EMPTY,
            function_distance=function_distance)

        sequence_dissimilarity = SequenceDissimilarity(
            annotation_task=annotation_task,
            list_admitted_symbols=list_admitted_symbols,
            symbol_dissimlarity_matrix=symbol_dissimilarity_matrix,
            DELTA_EMPTY=DELTA_EMPTY,
            function_cat=function_cat)

        super().__init__(annotation_task, DELTA_EMPTY, alpha, beta,
                         positional_dissimilarity,
                         sequence_dissimilarity)
