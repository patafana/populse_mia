
class DataViewer(object):

    '''
    Populse-MIA data viewers abstract base class: it just gives an API to be
    overloaded by subclasses.
    '''

    def display_files(self, files):
        '''
        Display the selected document files
        '''
        raise NotImplementedError(
            'display_files is abstract and should be overloaded in data '
            'viewer implementations')

    def clear(self):
        '''
        Hide / unload all displayed documents
        '''
        self.remove_files(self.displayed_files())

    def displayed_files(self):
        '''
        Get the list of displayed files
        '''
        raise NotImplementedError(
            'displayed_files is abstract and should be overloaded in data '
            'viewer implementations')

    def remove_files(self, files):
        '''
        Remove documents from the displayed ones (hide, unload...)
        '''
        raise NotImplementedError(
            'remove_files is abstract and should be overloaded in data '
            'viewer implementations')

    def set_documents(self, projet, documents):
        '''
        Sets the project and list of possible documents
        '''
        raise NotImplementedError(
            'set_documents is abstract and should be overloaded in data '
            'viewer implementations')


