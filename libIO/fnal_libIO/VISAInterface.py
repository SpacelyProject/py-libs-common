import pyvisa


#Run an interactive shell.
def VISA_shell():
    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()

    print("Available resources:")
    for i in range(len(resources)):
        print(f"{i}. {resources[i]}")

    resource_idx = int(input("Which one should we connect to?"))


    print(f"Attempting to configure {resources[resource_idx]} as an oscilloscope...")
    scope = Oscilloscope(None,resources[resource_idx])

    while True:
        user_input = input("cmd>")

        if user_input == "exit":
            break
        elif user_input == "curve":
            print(scope.get_wave())
        elif user_input == "onscreen":
            print(scope.onscreen())
        else:
            print(scope.query(user_input))

#VISA Interface

class VISAInterface(GenericInterface):


    def __init__(self, visa_resource):

        self.rm = pyvisa.ResourceManager()
        self.resources = self.rm.list_resources()


        if visa_resource not in self.resources:   
            self.log.error(f"Could not find resource {visa_resource}")
            self.log.debug(f"Resources:{self.resources}")
            return None

        self.inst = self.rm.open_resource(visa_resource)
        
        #Default timeout of 2 seconds for communicating.
        self.inst.timeout = 2000

    #VISA interface is automatically connected on initialization.
    def is_connected(self):
        return True

    #Generic query and write functions   
    def query(self, query_text):
        return self.inst.query(query_text)

    def write(self, write_text):
        return self.inst.write(write_text)
