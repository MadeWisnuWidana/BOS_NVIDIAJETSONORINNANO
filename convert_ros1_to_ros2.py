import re
import os

input_file = '/home/brone/LOKALISASI/Mas Alvin 21 (v1)-20260717T063348Z-1-001/Mas Alvin 21 (v1)/Lokalisasi.py'
output_file = '/home/brone/brone_vision_ws/remote_files/Lokalisasi_Alvin.py'

with open(input_file, 'r') as f:
    code = f.read()

# 1. Imports
code = code.replace("import rospy", "import rclpy\nfrom rclpy.node import Node\nfrom tf2_ros import TransformBroadcaster\nfrom geometry_msgs.msg import TransformStamped\nfrom rclpy.time import Time\nfrom rclpy.duration import Duration")
code = code.replace("import tf", "")

# 2. Node Class Definition
code = code.replace("class ImprovedOP3Localization:", "class ImprovedOP3Localization(Node):")
code = code.replace("rospy.init_node('improved_op3_localization')", "super().__init__('improved_op3_localization_alvin')")

# 3. Publishers and Subscribers
code = re.sub(r"self\.pose_pub = rospy\.Publisher\((.*?),\n*\s*(.*?),\n*\s*queue_size=(.*?)\)", r"self.pose_pub = self.create_publisher(\2, \1, \3)", code)
code = re.sub(r"self\.map_pub = rospy\.Publisher\((.*?),\n*\s*(.*?),\n*\s*queue_size=(.*?),\n*\s*latch=True\)", r"self.map_pub = self.create_publisher(\2, \1, \3)", code)
code = re.sub(r"self\.(.*?) = rospy\.Subscriber\((.*?),\n*\s*(.*?),\n*\s*(.*?)\)", r"self.\1 = self.create_subscription(\3, \2, \4, 10)", code)

# Fix image sub topic from /usb_cam_node/image_raw to /image_raw to match workspace
code = code.replace("'/usb_cam_node/image_raw'", "'/image_raw'")

# 4. Logging
code = code.replace("rospy.loginfo", "self.get_logger().info")
code = code.replace("rospy.logwarn", "self.get_logger().warn")
code = code.replace("rospy.logerr", "self.get_logger().error")
code = code.replace("rospy.logdebug", "self.get_logger().debug")

# 5. Time and Duration
code = code.replace("rospy.Time.now()", "self.get_clock().now().to_msg()")
# Fix specific case where time diff is calculated
code = code.replace("self.walking_start_time = rospy.Time.now()", "self.walking_start_time = self.get_clock().now()")
code = code.replace("self.last_ball_detection_time = rospy.Time.now()", "self.last_ball_detection_time = self.get_clock().now()")
code = code.replace("self.last_goal_detection_time = rospy.Time.now()", "self.last_goal_detection_time = self.get_clock().now()")
code = code.replace("self.last_update_time = rospy.Time.now()", "self.last_update_time = self.get_clock().now()")
code = code.replace("current_time = rospy.Time.now()", "current_time = self.get_clock().now()")
code = code.replace("'timestamp': rospy.Time.now()", "'timestamp': self.get_clock().now()")
# Diff time
code = code.replace("rospy.Duration(1.0)", "Duration(seconds=1.0)")
code = code.replace("(current_time - self.last_goal_detection_time) > self.goal_timeout", "(current_time.nanoseconds - self.last_goal_detection_time.nanoseconds) / 1e9 > 1.0")
code = code.replace("(current_time - self.last_ball_detection_time) > self.ball_timeout", "(current_time.nanoseconds - self.last_ball_detection_time.nanoseconds) / 1e9 > 1.0")

# 6. TF Broadcaster
code = code.replace("self.tf_broadcaster = tf.TransformBroadcaster()", "self.tf_broadcaster = TransformBroadcaster(self)")
# TF send transform replacement
tf_send_old = '''        self.tf_broadcaster.sendTransform(
            (pose[0], pose[1], 0),  # translation
            q,                      # rotation
            rospy.Time.now(),
            "base_footprint",
            "map"
        )'''
tf_send_new = '''        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'map'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = float(pose[0])
        t.transform.translation.y = float(pose[1])
        t.transform.translation.z = 0.0
        t.transform.rotation.x = q[0]
        t.transform.rotation.y = q[1]
        t.transform.rotation.z = q[2]
        t.transform.rotation.w = q[3]
        self.tf_broadcaster.sendTransform(t)'''
code = code.replace(tf_send_old, tf_send_new)
# Quaternion from Euler function replacement
code = code.replace("q = tf.transformations.quaternion_from_euler(0, 0, pose[2])", 
"""        cy = math.cos(pose[2] * 0.5)
        sy = math.sin(pose[2] * 0.5)
        cp = math.cos(0 * 0.5)
        sp = math.sin(0 * 0.5)
        cr = math.cos(0 * 0.5)
        sr = math.sin(0 * 0.5)
        q = [
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy
        ]""")

# 7. Odometry time diff (header.stamp in ROS2 has sec and nanosec)
odometry_dt_old = """            dt = (self.current_joint_states.header.stamp - 
                  self.previous_joint_states.header.stamp).to_sec()"""
odometry_dt_new = """            t_curr = Time.from_msg(self.current_joint_states.header.stamp)
            t_prev = Time.from_msg(self.previous_joint_states.header.stamp)
            dt = (t_curr.nanoseconds - t_prev.nanoseconds) / 1e9"""
code = code.replace(odometry_dt_old, odometry_dt_new)

# 8. Main Loop
main_loop_old = """    def run(self):
        \"\"\"Main run loop dengan penambahan pengecekan orientasi\"\"\"
        rate = rospy.Rate(30)  # 30Hz update rate
        
        try:
            while not rospy.is_shutdown():
                # Tentukan orientasi lapangan
                self.determine_field_orientation()
                
                # Update dan publish pose
                self.publish_pose()
                self.visualize()
                
                # Log status orientasi jika baru dikonfirmasi
                if self.field_orientation and not self.is_orientation_confirmed:
                    self.get_logger().info(f"Field orientation determined: {self.field_orientation}")
                    self.is_orientation_confirmed = True
                
                rate.sleep()
                
        except KeyboardInterrupt:
            self.get_logger().info("Shutting down OP3 Localization node...")
        
        finally:
            cv2.destroyAllWindows()"""

main_loop_new = """    def run_step(self):
        # Tentukan orientasi lapangan
        self.determine_field_orientation()
        # Update dan publish pose
        self.publish_pose()
        self.visualize()
        if self.field_orientation and not self.is_orientation_confirmed:
            self.get_logger().info(f"Field orientation determined: {self.field_orientation}")
            self.is_orientation_confirmed = True"""

code = code.replace(main_loop_old, main_loop_new)

# Remove cv2.imshow and waitKey to run headless
code = code.replace("cv2.imshow", "# cv2.imshow")
code = code.replace("cv2.waitKey", "# cv2.waitKey")
code = code.replace("cv2.namedWindow", "# cv2.namedWindow")

# 9. __main__ block
main_block_old = """if __name__ == '__main__':
    try:
        # Create custom message type for orientation
        from std_msgs.msg import Header
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--side', type=str, default='right',
                          choices=['right', 'left'],
                          help='Field side to initialize (right or left)')
        args = parser.parse_args()
        
        # Initialize and run localization with specified side
        localization = ImprovedOP3Localization(field_side=args.side)
        localization.run()
        
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        rospy.logerr(f"Error in OP3 Localization: {str(e)}")
        raise"""

main_block_new = """def main(args=None):
    rclpy.init(args=args)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--side', type=str, default='right',
                      choices=['right', 'left'],
                      help='Field side to initialize (right or left)')
    # Allow unknown args from ros2 run
    parsed_args, unknown = parser.parse_known_args()
    
    localization = ImprovedOP3Localization(field_side=parsed_args.side)
    timer_period = 1.0 / 30.0
    localization.timer = localization.create_timer(timer_period, localization.run_step)
    
    try:
        rclpy.spin(localization)
    except KeyboardInterrupt:
        pass
    finally:
        localization.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()"""

code = code.replace(main_block_old, main_block_new)
code = code.replace("rospy.ROSInterruptException", "Exception")
code = code.replace("rospy.is_shutdown()", "False") # Fallback for any other while loops

with open(output_file, 'w') as f:
    f.write(code)

print("Conversion complete!")
