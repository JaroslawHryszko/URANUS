######################################################################################
# URANUS: Ultra-light Risk ANalysis Using Stepwise Comparison                        #
# parameter_names - list ordered by parameter importance (from high to low priority) #
# (C) 2024 Department of Software Engineering, Jagiellonian University               #
######################################################################################

from datetime import datetime


def floor(n):
    return int(n - (n % 1))


class CustomError(Exception):

    def __init__(self, message):
        super().__init__(message)


class Uranus:

    def __init__(self, parameter_names, element_names):

        if not isinstance(parameter_names, list):
            raise CustomError("first parameter should be a list (possibly empty) of parameter names")
        if not isinstance(element_names, list):
            raise CustomError("second parameter should be a list (possibly empty) of element names")
        if len(set(parameter_names)) != len(parameter_names):
            raise CustomError("Names of the parameters must be unique")
        if len(set(element_names)) != len(element_names):
            raise CustomError("Names of the elements must be unique")

        self.log_file = './log.txt'  # default log name, can be changed using setLogFile()
        self.logging = True
        self.num_comparisons = 0
        self.p_names = parameter_names
        self.e_names = element_names
        self.num_parameters = len(parameter_names)
        self.num_elements = len(element_names)
        self.final_list = []  # final order

        self.prioritized = [[] for _ in range(len(parameter_names))]  # actual order for each parameter
        for i in range(len(parameter_names)):
            self.prioritized[i] = []

        self.next_elem = None
        self.next_parameter = None
        self.next_range = []  # a part of prioritized list to compare against, for a given parameter

        self.log("start")

    def set_log_file(self, name):
        self.log_file = name

    def set_logging(self, log_status):
        self.logging = log_status

    def log(self, msg):
        if self.logging:
            with open(self.log_file, 'a') as file:
                file.write(f"{datetime.now()}: {msg}\n")

    def get_parameter_names(self):
        return self.p_names

    def get_element_names(self):
        return self.e_names

    def rename_parameter(self, index, new_name):
        if not (new_name in self.p_names):
            self.p_names[index] = new_name
            self.log(f"Renamed parameter {index}: {self.p_names[index]} -> {new_name}")
            return True
        else:
            return False

    def rename_element(self, index, new_name):
        if not (new_name in self.e_names):
            self.e_names[index] = new_name
            self.log(f"Renamed element {index}: {self.e_names[index]} -> {new_name}")
            return True
        else:
            return False

    def add_element(self, name):
        if not (name in self.e_names):
            self.e_names.append(name)
            self.num_elements = self.num_elements + 1
            self.log(f"Added new element {self.num_elements-1}: {name}")
            return True
        return False

    def remove_element(self, idx):
        if idx < len(self.e_names):
            self.log(f"Removed element {idx}: {self.e_names[idx]}. Might rename indices > idx in prioritized, "
                     f"next_range and next_elem")
            self.prioritized = [[e for e in subList if e != idx] for subList in self.prioritized]
            self.next_range = [e for e in self.next_range if e != idx]
            # in prioritized and in nextRange lower by one the indices of all elements greater than idx
            self.prioritized = [[el - 1 if el > idx else el for el in sublist] for sublist in self.prioritized]
            self.next_range = [el - 1 if el > idx else el for el in self.next_range]
            self.num_elements = self.num_elements - 1
            self.e_names.pop(idx)
            if not (self.next_elem is None):
                if idx < self.next_elem:
                    self.next_elem = self.next_elem-1
                elif idx == self.next_elem:
                    self.next_range = []
                    self.next_elem = None
            return True
        else:
            return False

    def add_parameter(self, name):  # notice that a new parameter is added with the lowest priority
        if not (name in self.p_names):
            self.p_names.append(name)
            self.num_parameters = self.num_parameters + 1
            self.prioritized.append([])
            self.log(f"Added param {self.num_parameters-1}: {self.p_names[self.num_parameters-1]} (lowest priority)")
            return True
        else:
            return False

    def remove_parameter(self, idx):
        if idx < len(self.prioritized):
            self.log(f"Removed param {idx}: {self.p_names[idx]}. Might modify next_parameter, next_elem and "
                     f"next_range if next_parameter was removed")
            self.prioritized.pop(idx)
            self.p_names.pop(idx)
            self.num_parameters = self.num_parameters - 1
            if not (self.next_parameter is None):
                if self.next_parameter == idx:
                    self.next_parameter = None
                    self.next_elem = None
                    self.next_range = []
                elif self.next_parameter > idx:
                    self.next_parameter = self.next_parameter - 1
            return True
        else:
            return False

    def swap_parameter_priorities(self, index1, index2):
        if (index1 < len(self.p_names)) and (index2 < len(self.p_names)) and (index1 != index2):
            self.log(f"Swapped parameters {index1} and {index2}: {self.p_names[index1]} <-> {self.p_names[index2]}")
            tmp = self.prioritized[index1]
            self.prioritized[index1] = self.prioritized[index2]
            self.prioritized[index2] = tmp
            tmp = self.p_names[index1]
            self.p_names[index1] = self.p_names[index2]
            self.p_names[index2] = tmp
            if self.next_parameter == index1:
                self.next_parameter = index2
            elif self.next_parameter == index2:
                self.next_parameter = index1
            return True
        else:
            return False

    def is_done(self):
        if sum(len(innerList) for innerList in self.prioritized) == self.num_parameters * self.num_elements:
            return True
        else:
            return False

    def show_status(self):
        print(f"Parameters: {self.p_names}")
        print(f"Elements: {self.e_names}")
        for i in range(len(self.prioritized)):
            print(f"Parameter {i} ({self.p_names[i]}) : {self.prioritized[i]}")
        print(f"Next element: {self.next_elem}")
        print(f"Next parameter: {self.next_parameter}")
        print(f"Next range: {self.next_range}")
        print(f"Current number of comparisons: {self.num_comparisons}")
        print(f"Progress: {self.progress():.2f}%")

    @staticmethod
    def split_list_by_element(my_list, given_element):
        try:
            index_of_given_element = my_list.index(given_element)
            part1 = my_list[:index_of_given_element]
            part2 = my_list[index_of_given_element + 1:]
            return part1, part2
        except ValueError:
            print(f"{given_element} is not in the list.")
            return None, None

    def progress(self):
        total = self.num_parameters * self.num_elements
        if total == 0:
            return 0
        else:
            return 100 * sum(len(inner) for inner in self.prioritized) / (self.num_parameters * self.num_elements)

    def next_to_process(self):  # returns (elem1 to compare, elem2 to compare, parameter against which to compare)
        if self.is_done():
            return None, None, None
        if self.num_elements == 1:
            for i in range(len(self.p_names)):
                self.prioritized[i] = [0]
            return None, None, None

        if len(self.next_range) >= 1:
            compared_element = self.next_range[floor(len(self.next_range) / 2)]
        else:
            self.next_parameter = min(range(len(self.prioritized)), key=lambda j: len(self.prioritized[j]))
            remaining_elements = (set(range(0, self.num_elements))) - set(self.prioritized[self.next_parameter])
            self.next_elem = min(remaining_elements)
            if len(self.prioritized[self.next_parameter]) == 0:
                self.prioritized[self.next_parameter] = [self.next_elem]
                self.next_elem = min(remaining_elements - {self.next_elem})
            self.next_range = self.prioritized[self.next_parameter]
            compared_element = self.next_range[floor(len(self.next_range) / 2)]

        return self.next_elem, compared_element, self.next_parameter

    def set_priority(self, relation_type):  # type=0: lower, type=1: higher
        if not ((relation_type == 0) or (relation_type == 1)):
            raise CustomError("Wrong priority type - only 2 values are allowed: 0 (priority(nextElement) lower than "
                              "priority(elementToCompare) or 1 (priority(nextElement) higher than priority("
                              "elementToCompare)")

        if self.is_done():
            return None

        inserted = False
        self.num_comparisons = self.num_comparisons + 1
        # update prioritized table by inserting an element when you can do it; otherwise, restrict the search interval
        if len(self.next_range) == 0:
            raise CustomError("nextToProcess() must be used before invoking setPriority()")
        if len(self.next_range) == 1:
            l1, l2 = self.split_list_by_element(self.prioritized[self.next_parameter], self.next_range[0])
            if relation_type == 0:
                self.log(f"parameter {self.next_parameter}, {self.next_elem} < {self.next_range[0]}")
                self.prioritized[self.next_parameter] = l1 + [self.next_elem, self.next_range[0]] + l2
                inserted = True
            elif relation_type == 1:
                self.log(f"parameter {self.next_parameter}, {self.next_range[0]} < {self.next_elem}")
                self.prioritized[self.next_parameter] = l1 + [self.next_range[0], self.next_elem] + l2
                inserted = True
        elif len(self.next_range) == 2 and relation_type == 0:
            self.log(f"parameter {self.next_parameter}, {self.next_elem} < {self.next_range[1]}")
            self.next_range = [self.next_range[0]]
        elif len(self.next_range) == 2 and relation_type == 1:
            self.log(f"parameter {self.next_parameter}, {self.next_range[1]} < {self.next_elem}")
            l1, l2 = self.split_list_by_element(self.prioritized[self.next_parameter], self.next_range[1])
            self.prioritized[self.next_parameter] = l1 + [self.next_range[1], self.next_elem] + l2
            inserted = True
        elif len(self.next_range) > 2:
            next_second_element_index = floor(len(self.next_range) / 2)
            if relation_type == 0:
                self.log(f"param {self.next_parameter}, {self.next_elem}<{self.next_range[next_second_element_index]}")
                self.next_range = self.next_range[:next_second_element_index]
            else:
                self.log(f"param {self.next_parameter}, {self.next_range[next_second_element_index]}<{self.next_elem}")
                self.next_range = self.next_range[next_second_element_index + 1:]

        if inserted:
            self.next_range = []

    def prioritize(self, param, elements, priorities):
        if len(elements) == 0:
            return []
        elif len(elements) == 1:
            self.final_list.append(elements[0])
            return elements[0]
        elif param < self.num_parameters-1:
            # split elements according to next parameter (param+1) and sort two parts using recursion
            el_high = [e for e in priorities[param + 1][floor(len(priorities[param + 1]) / 2):] if e in elements]
            el_low = [e for e in priorities[param + 1][:floor(len(priorities[param + 1]) / 2)] if e in elements]
            return [self.prioritize(param + 1, el_high, priorities)] + [self.prioritize(param + 1, el_low, priorities)]
        else:
            # last parameter with more than 1 element: restrict to these points and start over
            new_all_prioritized = [[e for e in inner_list if e in elements] for inner_list in priorities]
            return self.prioritize(-1, elements, new_all_prioritized)

    def prioritized_list(self):
        if self.is_done() and self.num_parameters > 0:
            self.final_list = []
            self.prioritize(-1, list(range(self.num_elements)), self.prioritized)
            self.log(f"Prioritization done. Final prioritized list: {self.final_list}")
            return self.final_list
        else:
            return []
