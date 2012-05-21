"""Used to trigger service of an OBS project / package :

:term:`Workitem` fields IN:

:Parameters:
   :ev.namespace (string):
      Used to contact the right OBS instance.
   :package (string):
      Package name to be rebuilt
   :project (string):
      OBS project in which the package lives
   
   
:term:`Workitem` params IN

:Parameters:
   :package (string):
      Package name to be rebuilt, overrides the package field
   :project (string):
      OBS project in which the package lives, overrides the project field

:term:`Workitem` fields OUT:

:Returns:
   :result (Boolean):
      True if the everything went OK, False otherwise

"""

from boss.obs import BuildServiceParticipant
import osc

class ParticipantHandler(BuildServiceParticipant):
    """ Participant class as defined by the SkyNET API """

    def handle_wi_control(self, ctrl):
        """ job control thread """
        pass

    @BuildServiceParticipant.get_oscrc
    def handle_lifecycle_control(self, ctrl):
        """ participant control thread """
        pass

    @BuildServiceParticipant.setup_obs
    def handle_wi(self, wid):
        """ Workitem handling function """
        wid.result = False
        f = wid.fields
        p = wid.params

        if p.project and p.package:
            osc.core.runservice(self.obs.apiurl, p.project, p.package)
        elif f.project and f.package:
            osc.core.runservice(self.obs.apiurl, f.project, f.package)
        else:
            raise RuntimeError("Missing mandatory field or parameter: package, project")

        wid.result = True