-- Создаём таблицу студентов
CREATE TABLE students (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    city TEXT NOT NULL
);

-- Добавляем тестовые данные
INSERT INTO students (id, first_name, last_name, age, city)
VALUES
    (1, 'Ivan', 'Petrov', 20, 'Moscow'),
    (2, 'Anna', 'Sidorova', 22, 'London'),
    (3, 'Petr', 'Ivanov', 19, 'Berlin'),
    (4, 'Maria', 'Smirnova', 21, 'Paris'),
    (5, 'Alex', 'Brown', 23, 'London');
