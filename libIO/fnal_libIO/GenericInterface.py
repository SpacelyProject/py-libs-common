


#GenericInterface is a parent class which represents the interface that all
#instruments can expect.
#
# USAGE:




class GenericInterface():

    # __init__() --> Should initialize the connection to the device.
    def __init__(self):
        print("ERROR: Called GenericInterface.__init__()... You need to implement a specific interface.")
        pass

    # is_connected() --> Returns true iff the interface is initialized and ready to send/receive data.
    def is_connected(self) -> bool:
        print("ERROR: Called GenericInterface.is_connected()... You need to implement a specific interface.")
        return False

    # write() --> Should write a line w/o expecting a response.
    def write(self, write_text):
        print("ERROR: Called GenericInterface.write()... You need to implement a specific interface.")
        return
        
    # query() --> Should write a line and read back the response.
    def query(self, query_text):
        print("ERROR: Called GenericInterface.query()... You need to implement a specific interface.")
        return


