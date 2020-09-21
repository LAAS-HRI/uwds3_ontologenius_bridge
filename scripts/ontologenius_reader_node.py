#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import rospy
from uwds3_msgs.msg import WorldStamped
from uwds3_msgs.srv import Query
from pyuwds3.types.scene_node import SceneNode
from pyuwds3.types.temporal_situation import TemporalSituation
from ontologenius import OntologyManipulator


class OntologeniusReaderNode(object):
    """ The ontologenius reader which allow to query uwds3 entities with SPARQL-like queries """
    def __init__(self):
        """ Default constructor """

        self.ontologenius_client = OntologyManipulator()
        self.ontologenius_client.close()
        rospy.loginfo("[ontologenius_reader] Conected to Ontologenius !")

        self.created_nodes = {}
        self.scene_nodes = {}
        self.created_situations = {}

        self.uwds3_oro_id_map = {}
        self.oro_uwds3_id_map = {}

        self.support = {}
        self.graspable = {}
        self.container = {}
        self.movable = {}
        self.held_by = {}

        self.query_service = rospy.Service("uwds3/query_knowledge_base", Query, self.handle_query)

        input_world_topic = rospy.get_param("~input_world_topic", "corrected_tracks")
        rospy.loginfo("[ontologenius_reader] Connecting to '"+input_world_topic+"'...")
        self.world_subscriber = rospy.Subscriber(input_world_topic, WorldStamped, self.callback, queue_size=1)
        rospy.loginfo("[ontologenius_reader] Connected to Underworlds !")

    def handle_query(self, req, agent="myself"):
        """ Handle the query """
        try:

            query_tokens = req.query.split(",")
            result_nodes = []
            if len(query_tokens) > 1:
                results = self.kb.findForAgent(agent, query_tokens[0].split(" ")[0], query_tokens[1:])
            else:
                results = self.kb.findForAgent(agent, query_tokens[0].split(" ")[0], query_tokens)
            for node_id in results:
                if node_id in self.scene_nodes:
                    result_nodes.append(self.scene_nodes[node_id])
            return result_nodes, True, ""
        except Exception as e:
            rospy.logwarn("[ontologenius_reader] Exception occurred : "+str(e))
            return [], False, str(e)

    def callback(self, world_msg):
        """ World callback """
        scene_nodes = {}
        for node_msg in world_msg.world.scene:
            node = SceneNode().from_msg(node_msg)
            scene_nodes[node.id] = node
            if node.id not in self.created_nodes:
                self.add_scene_node(node)
                self.created_nodes[node.id] = True

        for situation_msg in world_msg.world.timeline:
            situation = TemporalSituation().from_msg(situation_msg)
            self.learn_affordance(situation)
            self.update_situation(situation)

        self.scene_nodes = scene_nodes

    def add_scene_node(self, scene_node, agent="myself"):
        """ Add the given scene node """
        types = []
        if scene_node.is_located():
            types.append("LocalizedThing")
        elif scene_node.has_shape():
            types.append("SolidTangibleThing")
        else:
            types.append("Thing")

        if scene_node.label == "myself":
            types.append("Robot")
        elif scene_node.label == "person":
            types.append("Human")
        else:
            pass

        for type in types:
            self.ontologenius_client.addObjectProperty(scene_node.id, "isA", type)

    def update_situation(self, situation, agent="myself"):
        """ Updates the given situations """
        if situation.predicate == "pick":
            if situation.object not in self.held_by:
                self.ontologenius_client.addObjectProperty(situation.object, "isInHand", situation.subject)
                self.held_by[situation.object] = situation.subject
        elif situation.predicate == "place":
            if situation.object in self.held_by:
                self.ontologenius_client.removeObjectProperty(situation.object, "isInHand", situation.subject)
                del self.held_by[situation.object]
        elif situation.predicate == "release":
            if situation.object in self.held_by:
                self.ontologenius_client.removeObjectProperty(situation.object, "isInHand", situation.subject)
                del self.held_by[situation.object]

        if situation.predicate == "in":
            if not situation.is_finished():
                self.ontologenius_client.addObjectProperty(situation.subject, "isIn", situation.object)
            else:
                self.ontologenius_client.removeObjectProperty(situation.subject, "isIn", situation.object)
        elif situation.predicate == "on":
            if not situation.is_finished():
                self.ontologenius_client.addObjectProperty(situation.subject, "isOn", situation.object)
            else:
                self.ontologenius_client.removeObjectProperty(situation.subject, "isOn", situation.object)
        elif situation.predicate == "close":
            if not situation.is_finished():
                self.ontologenius_client.addObjectProperty(situation.subject, "isClose", situation.object)
            else:
                self.ontologenius_client.removeObjectProperty(situation.subject, "isClose", situation.object)
        else:
            pass

    def learn_affordance(self, situation, agent="myself"):
        """ Learn the affordances from the physical reasoner """
        if situation.predicate == "pick":
            if situation.object not in self.graspable:
                self.ontologenius_client.addObjectProperty(situation.subject, "isA", "GraspableObject")
        elif situation.predicate == "on":
            if situation.object not in self.support:
                self.ontologenius_client.addObjectProperty(situation.object, "isA", "PhysicalSupport")
        elif situation.predicate == "in":
            if situation.object not in self.container:
                self.ontologenius_client.addObjectProperty(situation.object, "isA", "Container")

    def run(self):
        """ Run the component """
        while not rospy.is_shutdown():
            rospy.spin()


if __name__ == "__main__":
    rospy.init_node("ontologenius_reader", anonymous=True)
    recorder = OntologeniusReaderNode().run()