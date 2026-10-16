CREATE EXTENSION tcn;
CREATE TABLE builtin_tcn (id integer PRIMARY KEY);
CREATE TRIGGER builtin_tcn_change
    AFTER INSERT ON builtin_tcn
    FOR EACH ROW EXECUTE FUNCTION triggered_change_notification();
LISTEN tcn;
INSERT INTO builtin_tcn VALUES (91);
