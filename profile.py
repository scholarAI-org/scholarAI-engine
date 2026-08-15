class Student:
    def __init__(self, name, age, grade, major):
        self.name = name
        self.age = age
        self.grade = grade
        self.major = major
    
    def print_profile(self):
        print(f"Student Profile:")
        print(f"Name: {self.name}")
        print(f"Age: {self.age}")
        print(f"Grade: {self.grade}")
        print(f"Major: {self.major}")


# Example usage
if __name__ == "__main__":
    student = Student("John Doe", 20, "Sophomore", "Computer Science")
    student.print_profile()
